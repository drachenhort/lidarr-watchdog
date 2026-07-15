from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "lidarr-watchdog.db"
    seed_lidarr_url: str | None = None
    seed_lidarr_api_key: str | None = None
    seed_poll_interval: int | None = None

    @classmethod
    def from_env(cls) -> Config:
        port = cls._read_int("LIDARR_WATCHDOG_PORT", 8000)
        host = os.environ.get("LIDARR_WATCHDOG_HOST", "0.0.0.0")
        db_path = os.environ.get("LIDARR_WATCHDOG_DB_PATH", "lidarr-watchdog.db")

        seed_poll_interval = None
        if "LIDARR_WATCHDOG_POLL_INTERVAL" in os.environ:
            seed_poll_interval = cls._read_int("LIDARR_WATCHDOG_POLL_INTERVAL", 300)

        seed_lidarr_url = os.environ.get("LIDARR_URL")

        return cls(
            host=host,
            port=port,
            db_path=db_path,
            seed_lidarr_url=seed_lidarr_url.rstrip("/") if seed_lidarr_url else None,
            seed_lidarr_api_key=os.environ.get("LIDARR_API_KEY"),
            seed_poll_interval=seed_poll_interval,
        )

    @staticmethod
    def _read_int(env_var: str, default: int) -> int:
        raw = os.environ.get(env_var, str(default))
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigError(f"{env_var} must be an integer, got {raw!r}") from exc
