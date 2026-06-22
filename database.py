"""SQLite database for conversation context and message logging."""

import sqlite3
import time
from contextlib import contextmanager
from config import Config


def init_db():
    """Initialize database tables."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                wxid        TEXT NOT NULL,
                nickname    TEXT NOT NULL,
                role        TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content     TEXT NOT NULL,
                timestamp   REAL NOT NULL,
                msg_id      TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                msg_id      TEXT UNIQUE,
                wxid        TEXT NOT NULL,
                nickname    TEXT NOT NULL,
                content     TEXT NOT NULL,
                msg_type    INTEGER,
                is_group    INTEGER DEFAULT 0,
                group_name  TEXT,
                direction   TEXT NOT NULL CHECK(direction IN ('incoming', 'outgoing', 'forwarded')),
                timestamp   REAL NOT NULL,
                processed   INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS confirm_queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                msg_id      TEXT NOT NULL,
                wxid        TEXT NOT NULL,
                nickname    TEXT NOT NULL,
                content     TEXT NOT NULL,
                llm_reply   TEXT,
                reason      TEXT,
                status      TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'modified', 'skipped')),
                final_reply TEXT,
                created_at  REAL NOT NULL,
                resolved_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_conv_wxid ON conversations(wxid);
            CREATE INDEX IF NOT EXISTS idx_conv_ts ON conversations(timestamp);
            CREATE INDEX IF NOT EXISTS idx_msg_wxid ON messages(wxid);
            CREATE INDEX IF NOT EXISTS idx_confirm_status ON confirm_queue(status);
        """)


@contextmanager
def get_conn():
    """Context manager for database connections."""
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_message(msg_id: str, wxid: str, nickname: str, content: str,
                 msg_type: int = 1, is_group: bool = False,
                 group_name: str = "", direction: str = "incoming"):
    """Save a message to the messages table."""
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO messages
               (msg_id, wxid, nickname, content, msg_type, is_group, group_name, direction, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (msg_id, wxid, nickname, content, msg_type, int(is_group), group_name, direction, time.time()),
        )


def save_conversation(wxid: str, nickname: str, role: str, content: str, msg_id: str = ""):
    """Save a conversation turn."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (wxid, nickname, role, content, timestamp, msg_id) VALUES (?, ?, ?, ?, ?, ?)",
            (wxid, nickname, role, content, time.time(), msg_id),
        )


def get_conversation_history(wxid: str, limit: int = 20) -> list[dict]:
    """Get recent conversation history for a contact."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, timestamp FROM conversations WHERE wxid = ? ORDER BY timestamp DESC LIMIT ?",
            (wxid, limit),
        ).fetchall()
    # Reverse to chronological order
    rows = rows[::-1]
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def has_history(wxid: str) -> bool:
    """Check if we have conversation history with this contact."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM conversations WHERE wxid = ?", (wxid,)
        ).fetchone()
    return row["cnt"] > 0


def add_to_confirm_queue(msg_id: str, wxid: str, nickname: str, content: str,
                         llm_reply: str, reason: str) -> int:
    """Add a message to the confirmation queue. Returns queue entry id."""
    with get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO confirm_queue
               (msg_id, wxid, nickname, content, llm_reply, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (msg_id, wxid, nickname, content, llm_reply, reason, time.time()),
        )
        return cursor.lastrowid


def get_pending_confirmations() -> list[dict]:
    """Get all pending confirmation items."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM confirm_queue WHERE status = 'pending' ORDER BY created_at ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def resolve_confirmation(queue_id: int, status: str, final_reply: str = ""):
    """Mark a confirmation as resolved."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE confirm_queue SET status = ?, final_reply = ?, resolved_at = ? WHERE id = ?",
            (status, final_reply, time.time(), queue_id),
        )


def mark_message_processed(msg_id: str):
    """Mark a message as processed."""
    with get_conn() as conn:
        conn.execute("UPDATE messages SET processed = 1 WHERE msg_id = ?", (msg_id,))
