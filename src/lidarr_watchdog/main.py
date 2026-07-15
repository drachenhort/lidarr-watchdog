from __future__ import annotations

import logging
import sqlite3
import threading
import traceback

import uvicorn

from lidarr_watchdog import history, settings
from lidarr_watchdog.config import Config
from lidarr_watchdog.lidarr_client import LidarrClient
from lidarr_watchdog.watchdog import check_once, synthetic_deny_reason
from lidarr_watchdog.web import create_app

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


def _run_watchdog_loop(conn: sqlite3.Connection, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        count = run_check_cycle(conn)
        if count:
            logger.info("Handled %d failed import(s)", count)
        stop_event.wait(settings.get_poll_interval(conn))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = Config.from_env()
    conn = history.connect(config.db_path)

    settings.seed_if_unset(conn, "lidarr_url", config.seed_lidarr_url)
    settings.seed_if_unset(conn, "lidarr_api_key", config.seed_lidarr_api_key)
    if config.seed_poll_interval is not None:
        settings.seed_if_unset(conn, "poll_interval", str(config.seed_poll_interval))

    stop_event = threading.Event()
    watchdog_thread = threading.Thread(
        target=_run_watchdog_loop,
        args=(conn, stop_event),
        daemon=True,
    )
    watchdog_thread.start()

    app = create_app(conn)

    logger.info("Serving dashboard on %s:%s", config.host, config.port)
    try:
        uvicorn.run(app, host=config.host, port=config.port, log_level="info")
    finally:
        stop_event.set()
        watchdog_thread.join(timeout=5)
        logger.info("lidarr-watchdog stopped")


if __name__ == "__main__":
    main()
