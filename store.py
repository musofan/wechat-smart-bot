"""Suggestion store — persists suggestions to SQLite + JSONL append.

Each suggestion records what the bot would have said (in SUGGEST mode).
The JSONL file can be consumed by external monitoring tools.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import time
from pathlib import Path


class SuggestionStore:
    """Persist bot suggestions with dedup by (contact, hash(incoming)).

    Uses a per-instance temporary file by default to avoid shared-state races
    across tests. Pass an explicit ``db_path`` for production use.
    Call ``close()`` when done (or use as context manager).
    """

    def __init__(self, db_path: str = "", jsonl_path: str = ""):
        if db_path:
            resolved = db_path
        else:
            # Per-instance temp file avoids cross-test locking
            fd, resolved = tempfile.mkstemp(suffix=".db", prefix="suggestions_")
            import os
            os.close(fd)
        self._conn = sqlite3.connect(resolved, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._jsonl_path = Path(jsonl_path) if jsonl_path else None

    # ---- schema ----

    def init(self) -> None:
        """Create the suggestions table if it doesn't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS suggestions (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                contact            TEXT    NOT NULL,
                incoming_hash      TEXT    NOT NULL,
                incoming           TEXT    NOT NULL,
                draft_reply        TEXT    NOT NULL,
                needs_confirmation INTEGER NOT NULL DEFAULT 0,
                reason             TEXT    NOT NULL DEFAULT '',
                status             TEXT    NOT NULL DEFAULT 'suggested',
                ts                 REAL    NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_suggest_dedup
                ON suggestions(contact, incoming_hash);
            CREATE INDEX IF NOT EXISTS idx_suggest_status
                ON suggestions(status);
        """)
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ---- save ----

    def save(
        self,
        contact: str,
        incoming: str,
        draft_reply: str,
        needs_confirmation: bool = False,
        reason: str = "",
        status: str = "suggested",
    ) -> bool:
        """Persist a suggestion. Returns True if inserted, False if duplicate."""
        h = self._hash(incoming)
        ts = time.time()
        try:
            self._conn.execute(
                """INSERT INTO suggestions
                   (contact, incoming_hash, incoming, draft_reply,
                    needs_confirmation, reason, status, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (contact, h, incoming, draft_reply,
                 int(needs_confirmation), reason, status, ts),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            return False  # duplicate

        # JSONL append
        self._append_jsonl({
            "ts": ts,
            "contact": contact,
            "incoming": incoming,
            "draft_reply": draft_reply,
            "needs_confirmation": needs_confirmation,
            "reason": reason,
            "status": status,
        })
        return True

    # ---- query ----

    def list_recent(self, limit: int = 50) -> list[dict]:
        """Return the most recent suggestions."""
        rows = self._conn.execute(
            "SELECT * FROM suggestions ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def exists(self, contact: str, incoming: str) -> bool:
        """Check if a suggestion already exists (by dedup key)."""
        h = self._hash(incoming)
        row = self._conn.execute(
            "SELECT 1 FROM suggestions WHERE contact = ? AND incoming_hash = ?",
            (contact, h),
        ).fetchone()
        return row is not None

    def list_pending(self, limit: int = 20) -> list[dict]:
        """Return suggestions with status='suggested', oldest first."""
        rows = self._conn.execute(
            """SELECT * FROM suggestions
               WHERE status = 'suggested'
               ORDER BY ts ASC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_status(self, sid: int, status: str) -> bool:
        """Update the status of a suggestion. Returns True if updated."""
        cur = self._conn.execute(
            "UPDATE suggestions SET status = ? WHERE id = ?",
            (status, sid),
        )
        self._conn.commit()
        return cur.rowcount > 0

    # ---- helpers ----

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _append_jsonl(self, record: dict) -> None:
        if self._jsonl_path is None:
            return
        self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with self._jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
