from __future__ import annotations

import logging
import sqlite3
import threading
import traceback

import uvicorn

from lidarr_watchdog import history
from lidarr_watchdog.config import Config
from lidarr_watchdog.lidarr_client import LidarrClient
from lidarr_watchdog.watchdog import check_once
from lidarr_watchdog.web import create_app

logger = logging.getLogger(__name__)


def check_and_record(client: LidarrClient, conn: sqlite3.Connection) -> int:
    error = None
    failed_count = 0
    try:
        failed_count = check_once(
            client,
            on_blocklisted=lambda record: history.record_blocklist_event(
                conn,
                queue_id=record["id"],
                title=record.get("title", "<unknown>"),
                messages="; ".join(
                    message
                    for status_message in record.get("statusMessages", [])
                    for message in status_message.get("messages", [])
                ),
            ),
        )
    except Exception:
        logger.exception("Error while checking queue")
        error = traceback.format_exc()

    history.record_check(conn, failed_count=failed_count, error=error)
    return failed_count


def _run_watchdog_loop(
    client: LidarrClient, conn: sqlite3.Connection, poll_interval: int, stop_event: threading.Event
) -> None:
    while not stop_event.is_set():
        count = check_and_record(client, conn)
        if count:
            logger.info("Handled %d failed import(s)", count)
        stop_event.wait(poll_interval)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = Config.from_env()
    client = LidarrClient(config.lidarr_url, config.api_key)
    conn = history.connect(config.db_path)

    stop_event = threading.Event()
    watchdog_thread = threading.Thread(
        target=_run_watchdog_loop,
        args=(client, conn, config.poll_interval, stop_event),
        daemon=True,
    )
    watchdog_thread.start()

    app = create_app(conn, config.poll_interval)

    logger.info(
        "Serving dashboard on %s:%s, polling every %ss", config.host, config.port, config.poll_interval
    )
    try:
        uvicorn.run(app, host=config.host, port=config.port, log_level="info")
    finally:
        stop_event.set()
        watchdog_thread.join(timeout=5)
        logger.info("lidarr-watchdog stopped")


if __name__ == "__main__":
    main()
