from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from lidarr_watchdog import settings

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

CREATE TABLE IF NOT EXISTS repeat_counts (
    album_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (album_id, reason)
);

CREATE TABLE IF NOT EXISTS blocklist_only_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    queue_id INTEGER NOT NULL,
    album_id INTEGER,
    title TEXT NOT NULL,
    messages TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ignore_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    queue_id INTEGER NOT NULL,
    album_id INTEGER,
    artist_id INTEGER,
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
    settings.ensure_schema(conn)
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


def get_repeat_count(conn: sqlite3.Connection, album_id: int, reason: str) -> int:
    row = conn.execute(
        "SELECT count FROM repeat_counts WHERE album_id = ? AND reason = ?", (album_id, reason)
    ).fetchone()
    return row["count"] if row else 0


def increment_repeat_count(conn: sqlite3.Connection, album_id: int, reason: str) -> int:
    with _write_lock:
        conn.execute(
            "INSERT INTO repeat_counts (album_id, reason, count) VALUES (?, ?, 1) "
            "ON CONFLICT(album_id, reason) DO UPDATE SET count = count + 1",
            (album_id, reason),
        )
        conn.commit()
    return get_repeat_count(conn, album_id, reason)


def record_blocklist_only_event(
    conn: sqlite3.Connection, *, queue_id: int, album_id: int | None, title: str, messages: str
) -> None:
    with _write_lock:
        conn.execute(
            "INSERT INTO blocklist_only_events (occurred_at, queue_id, album_id, title, messages) "
            "VALUES (?, ?, ?, ?, ?)",
            (_now(), queue_id, album_id, title, messages),
        )
        conn.commit()


def get_recent_blocklist_only_events(conn: sqlite3.Connection, limit: int = 100) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM blocklist_only_events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


def record_ignore_event(
    conn: sqlite3.Connection,
    *,
    queue_id: int,
    album_id: int | None,
    artist_id: int | None,
    title: str,
    messages: str,
) -> None:
    with _write_lock:
        conn.execute(
            "INSERT INTO ignore_events (occurred_at, queue_id, album_id, artist_id, title, messages) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_now(), queue_id, album_id, artist_id, title, messages),
        )
        conn.commit()


def get_recent_ignore_events(conn: sqlite3.Connection, limit: int = 100) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM ignore_events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
