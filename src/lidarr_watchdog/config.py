from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    lidarr_url: str
    api_key: str
    poll_interval: int = 300

    @classmethod
    def from_env(cls) -> Config:
        url = os.environ.get("LIDARR_URL")
        api_key = os.environ.get("LIDARR_API_KEY")
        if not url:
            raise ConfigError("LIDARR_URL environment variable is not set")
        if not api_key:
            raise ConfigError("LIDARR_API_KEY environment variable is not set")

        raw_interval = os.environ.get("LIDARR_WATCHDOG_POLL_INTERVAL", "300")
        try:
            poll_interval = int(raw_interval)
        except ValueError as exc:
            raise ConfigError(
                f"LIDARR_WATCHDOG_POLL_INTERVAL must be an integer, got {raw_interval!r}"
            ) from exc

        return cls(lidarr_url=url.rstrip("/"), api_key=api_key, poll_interval=poll_interval)
