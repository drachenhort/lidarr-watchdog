from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TEXT NOT NULL,
    failed_count INTEGER NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS blocklist_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    queue_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    messages TEXT NOT NULL
);
"""

_write_lock = threading.Lock()


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def record_check(conn: sqlite3.Connection, *, failed_count: int, error: str | None = None) -> None:
    with _write_lock:
        conn.execute(
            "INSERT INTO checks (checked_at, failed_count, error) VALUES (?, ?, ?)",
            (_now(), failed_count, error),
        )
        conn.commit()


def record_blocklist_event(
    conn: sqlite3.Connection, *, queue_id: int, title: str, messages: str
) -> None:
    with _write_lock:
        conn.execute(
            "INSERT INTO blocklist_events (occurred_at, queue_id, title, messages) VALUES (?, ?, ?, ?)",
            (_now(), queue_id, title, messages),
        )
        conn.commit()


def get_last_check(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM checks ORDER BY id DESC LIMIT 1").fetchone()


def get_recent_events(conn: sqlite3.Connection, limit: int = 100) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM blocklist_events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
