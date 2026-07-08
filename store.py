"""Suggestion store: persists drafted (un-sent) replies for operator review, with
dedup by (contact, incoming). SQLite + an append-only JSONL mirror."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path


class SuggestionStore:
    def __init__(self, db_path, jsonl_path, clock=time.time):
        self.db_path = str(db_path)
        self.jsonl_path = str(jsonl_path)
        self.clock = clock
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.jsonl_path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self):
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS suggestions(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    contact TEXT,
                    incoming TEXT,
                    draft_reply TEXT,
                    needs_confirmation INTEGER DEFAULT 0,
                    reason TEXT,
                    status TEXT DEFAULT 'suggested',
                    dedup_key TEXT UNIQUE
                )"""
            )

    @staticmethod
    def _key(contact: str, incoming: str) -> str:
        return hashlib.md5(f"{contact}\x00{incoming}".encode("utf-8")).hexdigest()

    def add(self, contact: str, incoming: str, draft_reply: str,
            needs_confirmation: bool = False, reason: str = "") -> bool:
        """Insert a suggestion. Returns True if new, False if a duplicate."""
        ts = self.clock()
        key = self._key(contact, incoming)
        try:
            with sqlite3.connect(self.db_path) as c:
                c.execute(
                    """INSERT INTO suggestions
                       (ts, contact, incoming, draft_reply, needs_confirmation, reason, dedup_key)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (ts, contact, incoming, draft_reply, int(needs_confirmation), reason, key),
                )
        except sqlite3.IntegrityError:
            return False
        rec = {
            "ts": ts, "contact": contact, "incoming": incoming,
            "draft_reply": draft_reply, "needs_confirmation": bool(needs_confirmation),
            "reason": reason, "status": "suggested",
        }
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True

    def count(self) -> int:
        with sqlite3.connect(self.db_path) as c:
            return c.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0]
