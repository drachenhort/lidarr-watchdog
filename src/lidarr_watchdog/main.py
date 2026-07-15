from __future__ import annotations

import logging
import signal
import threading

from lidarr_watchdog.config import Config
from lidarr_watchdog.lidarr_client import LidarrClient
from lidarr_watchdog.watchdog import check_once

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = Config.from_env()
    client = LidarrClient(config.lidarr_url, config.api_key)

    stop_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda signum, frame: stop_event.set())
    signal.signal(signal.SIGINT, lambda signum, frame: stop_event.set())

    logger.info("lidarr-watchdog started, polling every %ss", config.poll_interval)
    while not stop_event.is_set():
        try:
            count = check_once(client)
            if count:
                logger.info("Handled %d failed import(s)", count)
        except Exception:
            logger.exception("Error while checking queue")

        stop_event.wait(config.poll_interval)

    logger.info("lidarr-watchdog stopped")


if __name__ == "__main__":
    main()
