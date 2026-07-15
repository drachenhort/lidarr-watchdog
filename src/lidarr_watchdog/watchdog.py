from __future__ import annotations

import logging
import re
from typing import Any, Callable

from lidarr_watchdog.lidarr_client import LidarrClient

logger = logging.getLogger(__name__)

ARCHIVE_EXTENSION_RE = re.compile(r"\.(rar|zip|7z|r\d{2,3})$", re.IGNORECASE)


def is_failed_import(record: dict[str, Any]) -> bool:
    return record.get("trackedDownloadState") == "importFailed"


def is_archive(record: dict[str, Any]) -> bool:
    title = record.get("title") or ""
    return bool(ARCHIVE_EXTENSION_RE.search(title))


def _status_messages(record: dict[str, Any]) -> list[str]:
    return [
        message
        for status_message in record.get("statusMessages", [])
        for message in status_message.get("messages", [])
    ]


def check_once(
    client: LidarrClient,
    on_blocklisted: Callable[[dict[str, Any]], None] | None = None,
    deny_archives: bool = False,
) -> int:
    queue = client.get_queue()
    to_deny = [
        record
        for record in queue
        if is_failed_import(record) or (deny_archives and is_archive(record))
    ]

    for record in to_deny:
        title = record.get("title", "<unknown>")
        messages = _status_messages(record)
        if not messages and is_archive(record):
            messages = ["Archive file detected (deny archives is enabled)"]
        logger.warning("Denying queue item: %s (%s)", title, "; ".join(messages) or "no details")

        client.remove_from_queue(record["id"], blocklist=True, skip_redownload=False)
        logger.info("Blocklisted and requeued for search: %s", title)

        if on_blocklisted:
            on_blocklisted(record)

    return len(to_deny)
