from __future__ import annotations

import logging
import sqlite3

from lidarr_watchdog import history, settings
from lidarr_watchdog.lidarr_client import LidarrClient
from lidarr_watchdog.watchdog import check_once, resolved_messages

logger = logging.getLogger(__name__)

# Reuse one LidarrClient (and its underlying requests.Session/connection
# pool) per sqlite3.Connection instead of paying a fresh TCP/TLS handshake
# on every poll cycle and every blocklist page view. Keyed by id(conn) since
# sqlite3.Connection supports neither weak references nor arbitrary
# attributes; invalidated automatically whenever the URL/API key change.
_client_cache: dict[int, tuple[str, str, LidarrClient]] = {}


def resolve_client(conn: sqlite3.Connection) -> LidarrClient | None:
    url = settings.get_lidarr_url(conn)
    api_key = settings.get_lidarr_api_key(conn)
    if not url or not api_key:
        _client_cache.pop(id(conn), None)
        return None
    cached = _client_cache.get(id(conn))
    if cached is not None and cached[0] == url and cached[1] == api_key:
        return cached[2]
    client = LidarrClient(url, api_key)
    _client_cache[id(conn)] = (url, api_key, client)
    return client


def _event_messages(record: dict, deny_archives: bool, deny_executables: bool) -> str:
    return "; ".join(resolved_messages(record, deny_archives, deny_executables))


def _category(reason: str) -> str:
    """Repeat-tracking bucket: failed imports are tracked separately from
    archive/executable denials, since they escalate to different actions."""
    return "failed_import" if reason == "failed_import" else "denied"


def _resolve_skip_redownload(
    record: dict,
    reason: str,
    conn: sqlite3.Connection,
    repeat_threshold: int,
    repeat_counts: dict[tuple[int, str], int],
) -> bool:
    album_id = record.get("albumId")
    if not album_id:
        return False
    category = _category(reason)
    count = history.increment_repeat_count(conn, album_id, category)
    # Cache the just-incremented count so _on_deny (called right after, for
    # the same record) doesn't need a second DB read and doesn't silently
    # depend on call order for correctness — if it's ever invoked without
    # this having run first, the cache miss below falls back to a fresh read.
    repeat_counts[(album_id, category)] = count
    return count >= repeat_threshold


def _on_deny(
    record: dict,
    reason: str,
    conn: sqlite3.Connection,
    client: LidarrClient,
    repeat_threshold: int,
    deny_archives: bool,
    deny_executables: bool,
    repeat_counts: dict[tuple[int, str], int],
) -> None:
    album_id = record.get("albumId")
    artist_id = record.get("artistId")
    title = record.get("title", "<unknown>")
    messages = _event_messages(record, deny_archives, deny_executables)
    queue_id = record["id"]
    category = _category(reason)
    if not album_id:
        count = 0
    else:
        count = repeat_counts.get((album_id, category))
        if count is None:
            count = history.get_repeat_count(conn, album_id, category)

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
    repeat_counts: dict[tuple[int, str], int] = {}
    try:
        failed_count = check_once(
            client,
            on_blocklisted=lambda record, reason: _on_deny(
                record,
                reason,
                conn,
                client,
                repeat_threshold,
                deny_archives,
                deny_executables,
                repeat_counts,
            ),
            deny_archives=deny_archives,
            deny_executables=deny_executables,
            resolve_skip_redownload=lambda record, reason: _resolve_skip_redownload(
                record, reason, conn, repeat_threshold, repeat_counts
            ),
        )
    except Exception as exc:
        # Full traceback goes to the logs; only a short summary is persisted
        # so a long Lidarr outage doesn't fill the checks table with
        # duplicated tracebacks (see history._MAX_CHECK_ROWS for the cap).
        logger.exception("Error while checking queue")
        error = str(exc) or type(exc).__name__

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
