from __future__ import annotations

import logging
import re
from typing import Any, Callable

from lidarr_watchdog.lidarr_client import LidarrClient

logger = logging.getLogger(__name__)

ARCHIVE_EXTENSION_RE = re.compile(r"\.(rar|zip|7z|r\d{2,3})$", re.IGNORECASE)
EXECUTABLE_EXTENSION_RE = re.compile(r"\.(exe|msi|bat|cmd|com|scr|vbs|ps1)$", re.IGNORECASE)


def is_failed_import(record: dict[str, Any]) -> bool:
    return record.get("trackedDownloadState") == "importFailed"


def is_archive(record: dict[str, Any]) -> bool:
    title = record.get("title") or ""
    return bool(ARCHIVE_EXTENSION_RE.search(title))


def is_executable(record: dict[str, Any]) -> bool:
    title = record.get("title") or ""
    return bool(EXECUTABLE_EXTENSION_RE.search(title))


def status_messages(record: dict[str, Any]) -> list[str]:
    """Flatten and deduplicate a queue record's statusMessages, preserving
    order. Lidarr emits one statusMessages entry per track, so an album-level
    issue (e.g. "Album match is not close enough") is repeated once per
    track without this — a 12-track album would otherwise show the same
    message 12 times."""
    all_messages = (
        message
        for status_message in record.get("statusMessages", [])
        for message in status_message.get("messages", [])
    )
    return list(dict.fromkeys(all_messages))


def synthetic_deny_reason(record: dict[str, Any], deny_archives: bool, deny_executables: bool) -> str | None:
    if deny_archives and is_archive(record):
        return "Archive file detected (deny archives is enabled)"
    if deny_executables and is_executable(record):
        return "Executable file detected (deny executables is enabled)"
    return None


def resolved_messages(
    record: dict[str, Any], deny_archives: bool, deny_executables: bool
) -> list[str]:
    """The messages to log/persist for a denied record: Lidarr's own
    statusMessages, or a synthetic archive/executable reason when Lidarr
    didn't provide any. Single source of truth for both the denial log line
    and the history event, so they can't silently drift apart."""
    messages = status_messages(record)
    if messages:
        return messages
    synthetic = synthetic_deny_reason(record, deny_archives, deny_executables)
    return [synthetic] if synthetic else []


def _classify(record: dict[str, Any], deny_archives: bool, deny_executables: bool) -> str | None:
    if is_failed_import(record):
        return "failed_import"
    if deny_archives and is_archive(record):
        return "archive"
    if deny_executables and is_executable(record):
        return "executable"
    return None


def check_once(
    client: LidarrClient,
    on_blocklisted: Callable[[dict[str, Any], str], None] | None = None,
    deny_archives: bool = False,
    deny_executables: bool = False,
    resolve_skip_redownload: Callable[[dict[str, Any], str], bool] | None = None,
) -> int:
    queue = client.get_queue()
    to_deny = []
    for record in queue:
        reason = _classify(record, deny_archives, deny_executables)
        if reason is not None:
            to_deny.append((record, reason))

    denied_count = 0
    for record, reason in to_deny:
        title = record.get("title", "<unknown>")
        messages = resolved_messages(record, deny_archives, deny_executables)
        logger.warning("Denying queue item: %s (%s)", title, "; ".join(messages) or "no details")

        skip_redownload = resolve_skip_redownload(record, reason) if resolve_skip_redownload else False
        client.remove_from_queue(record["id"], blocklist=True, skip_redownload=skip_redownload)
        logger.info("Blocklisted and requeued for search: %s", title)
        denied_count += 1

        if on_blocklisted:
            try:
                on_blocklisted(record, reason)
            except Exception:
                # The item is already removed/blocklisted in Lidarr at this
                # point; a failure recording it to history shouldn't lose
                # that count or abort denial of the rest of this cycle's
                # queue.
                logger.exception("Error handling blocklisted item: %s", title)

    return denied_count
