from __future__ import annotations

import logging
import sqlite3
import traceback

from lidarr_watchdog import history, settings
from lidarr_watchdog.lidarr_client import LidarrClient
from lidarr_watchdog.watchdog import check_once, synthetic_deny_reason

logger = logging.getLogger(__name__)


def resolve_client(conn: sqlite3.Connection) -> LidarrClient | None:
    url = settings.get_lidarr_url(conn)
    api_key = settings.get_lidarr_api_key(conn)
    if not url or not api_key:
        return None
    return LidarrClient(url, api_key)


def _event_messages(record: dict, deny_archives: bool, deny_executables: bool) -> str:
    messages = "; ".join(
        message
        for status_message in record.get("statusMessages", [])
        for message in status_message.get("messages", [])
    )
    if not messages:
        return synthetic_deny_reason(record, deny_archives, deny_executables) or ""
    return messages


def check_and_record(client: LidarrClient, conn: sqlite3.Connection) -> int:
    error = None
    failed_count = 0
    deny_archives = settings.get_deny_archives(conn)
    deny_executables = settings.get_deny_executables(conn)
    try:
        failed_count = check_once(
            client,
            on_blocklisted=lambda record: history.record_blocklist_event(
                conn,
                queue_id=record["id"],
                title=record.get("title", "<unknown>"),
                messages=_event_messages(record, deny_archives, deny_executables),
            ),
            deny_archives=deny_archives,
            deny_executables=deny_executables,
        )
    except Exception:
        logger.exception("Error while checking queue")
        error = traceback.format_exc()

    history.record_check(conn, failed_count=failed_count, error=error)
    return failed_count


def run_check_cycle(conn: sqlite3.Connection) -> int:
    client = resolve_client(conn)
    if client is None:
        history.record_check(
            conn, failed_count=0, error="Lidarr isn't configured — set the URL and API key in Settings"
        )
        return 0
    return check_and_record(client, conn)
