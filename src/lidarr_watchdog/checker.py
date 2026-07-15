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


def _category(reason: str) -> str:
    """Repeat-tracking bucket: failed imports are tracked separately from
    archive/executable denials, since they escalate to different actions."""
    return "failed_import" if reason == "failed_import" else "denied"


def _resolve_skip_redownload(
    record: dict, reason: str, conn: sqlite3.Connection, repeat_threshold: int
) -> bool:
    album_id = record.get("albumId")
    if not album_id:
        return False
    count = history.increment_repeat_count(conn, album_id, _category(reason))
    return count >= repeat_threshold


def _on_deny(
    record: dict,
    reason: str,
    conn: sqlite3.Connection,
    client: LidarrClient,
    repeat_threshold: int,
    deny_archives: bool,
    deny_executables: bool,
) -> None:
    album_id = record.get("albumId")
    artist_id = record.get("artistId")
    title = record.get("title", "<unknown>")
    messages = _event_messages(record, deny_archives, deny_executables)
    queue_id = record["id"]
    category = _category(reason)
    count = history.get_repeat_count(conn, album_id, category) if album_id else 0

    if not album_id or count < repeat_threshold:
        history.record_blocklist_event(conn, queue_id=queue_id, title=title, messages=messages)
        return

    if category == "failed_import":
        # Repeated failed imports for the same album: stop auto-researching
        # it (skip_redownload already handled that), but leave the album
        # monitored — a manual/future grab could still succeed.
        history.record_blocklist_only_event(
            conn, queue_id=queue_id, album_id=album_id, title=title, messages=messages
        )
    else:
        # Repeated archive/executable denials mean the album's available
        # releases are mostly undesirable files — blocklisting individual
        # releases won't stop Lidarr grabbing the next one, so tell Lidarr
        # to stop monitoring the album entirely.
        try:
            client.unmonitor_album(album_id)
        except Exception:
            logger.exception("Failed to unmonitor album %s in Lidarr", album_id)
        history.record_ignore_event(
            conn,
            queue_id=queue_id,
            album_id=album_id,
            artist_id=artist_id,
            title=title,
            messages=messages,
        )


def check_and_record(client: LidarrClient, conn: sqlite3.Connection) -> int:
    error = None
    failed_count = 0
    deny_archives = settings.get_deny_archives(conn)
    deny_executables = settings.get_deny_executables(conn)
    repeat_threshold = settings.get_repeat_threshold(conn)
    try:
        failed_count = check_once(
            client,
            on_blocklisted=lambda record, reason: _on_deny(
                record, reason, conn, client, repeat_threshold, deny_archives, deny_executables
            ),
            deny_archives=deny_archives,
            deny_executables=deny_executables,
            resolve_skip_redownload=lambda record, reason: _resolve_skip_redownload(
                record, reason, conn, repeat_threshold
            ),
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
