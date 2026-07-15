from __future__ import annotations

import logging
import sqlite3
import threading

import uvicorn

from lidarr_watchdog import history, settings
from lidarr_watchdog.checker import run_check_cycle
from lidarr_watchdog.config import Config
from lidarr_watchdog.web import create_app

logger = logging.getLogger(__name__)


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
