from __future__ import annotations

import sqlite3
import threading

DEFAULT_POLL_INTERVAL = 300

POLL_INTERVAL_UNIT_SECONDS = {
    "seconds": 1,
    "minutes": 60,
    "hours": 3600,
    "days": 86400,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_write_lock = threading.Lock()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def get(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set(conn: sqlite3.Connection, key: str, value: str) -> None:
    with _write_lock:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()


def seed_if_unset(conn: sqlite3.Connection, key: str, value: str | None) -> None:
    if value is not None and get(conn, key) is None:
        set(conn, key, value)


def get_lidarr_url(conn: sqlite3.Connection) -> str | None:
    return get(conn, "lidarr_url")


def get_lidarr_api_key(conn: sqlite3.Connection) -> str | None:
    return get(conn, "lidarr_api_key")


def get_poll_interval(conn: sqlite3.Connection) -> int:
    raw = get(conn, "poll_interval")
    return int(raw) if raw else DEFAULT_POLL_INTERVAL


def split_poll_interval(total_seconds: int) -> tuple[int, str]:
    """Split a total-seconds value into a (value, unit) pair for display,
    picking the largest unit that divides it evenly."""
    for unit in ("days", "hours", "minutes"):
        divisor = POLL_INTERVAL_UNIT_SECONDS[unit]
        if total_seconds % divisor == 0:
            return total_seconds // divisor, unit
    return total_seconds, "seconds"


def format_poll_interval(total_seconds: int) -> str:
    value, unit = split_poll_interval(total_seconds)
    return f"{value} {unit if value != 1 else unit.rstrip('s')}"


def get_deny_archives(conn: sqlite3.Connection) -> bool:
    return get(conn, "deny_archives") == "1"


def set_deny_archives(conn: sqlite3.Connection, value: bool) -> None:
    set(conn, "deny_archives", "1" if value else "0")


def get_deny_executables(conn: sqlite3.Connection) -> bool:
    return get(conn, "deny_executables") == "1"


def set_deny_executables(conn: sqlite3.Connection, value: bool) -> None:
    set(conn, "deny_executables", "1" if value else "0")
