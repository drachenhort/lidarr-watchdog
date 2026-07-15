from __future__ import annotations

import logging
from typing import Any, Callable

from lidarr_watchdog.lidarr_client import LidarrClient

logger = logging.getLogger(__name__)


def is_failed_import(record: dict[str, Any]) -> bool:
    return record.get("trackedDownloadState") == "importFailed"


def check_once(
    client: LidarrClient, on_blocklisted: Callable[[dict[str, Any]], None] | None = None
) -> int:
    failed = [record for record in client.get_queue() if is_failed_import(record)]

    for record in failed:
        title = record.get("title", "<unknown>")
        messages = [
            message
            for status_message in record.get("statusMessages", [])
            for message in status_message.get("messages", [])
        ]
        logger.warning("Failed import: %s (%s)", title, "; ".join(messages) or "no details")

        client.remove_from_queue(record["id"], blocklist=True, skip_redownload=False)
        logger.info("Blocklisted and requeued for search: %s", title)

        if on_blocklisted:
            on_blocklisted(record)

    return len(failed)
