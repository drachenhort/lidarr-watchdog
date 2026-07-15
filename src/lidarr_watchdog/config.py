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
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "lidarr-watchdog.db"

    @classmethod
    def from_env(cls) -> Config:
        url = os.environ.get("LIDARR_URL")
        api_key = os.environ.get("LIDARR_API_KEY")
        if not url:
            raise ConfigError("LIDARR_URL environment variable is not set")
        if not api_key:
            raise ConfigError("LIDARR_API_KEY environment variable is not set")

        poll_interval = cls._read_int("LIDARR_WATCHDOG_POLL_INTERVAL", 300)
        port = cls._read_int("LIDARR_WATCHDOG_PORT", 8000)
        host = os.environ.get("LIDARR_WATCHDOG_HOST", "0.0.0.0")
        db_path = os.environ.get("LIDARR_WATCHDOG_DB_PATH", "lidarr-watchdog.db")

        return cls(
            lidarr_url=url.rstrip("/"),
            api_key=api_key,
            poll_interval=poll_interval,
            host=host,
            port=port,
            db_path=db_path,
        )

    @staticmethod
    def _read_int(env_var: str, default: int) -> int:
        raw = os.environ.get(env_var, str(default))
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigError(f"{env_var} must be an integer, got {raw!r}") from exc
