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
    auth_username: str | None = None
    auth_password: str | None = None
    skip_auth_for_local: bool = False

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
            auth_username=os.environ.get("LIDARR_WATCHDOG_USERNAME") or None,
            auth_password=os.environ.get("LIDARR_WATCHDOG_PASSWORD") or None,
            skip_auth_for_local=cls._read_bool("LIDARR_WATCHDOG_SKIP_AUTH_FOR_LOCAL"),
        )

    @staticmethod
    def _read_int(env_var: str, default: int) -> int:
        raw = os.environ.get(env_var, str(default))
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigError(f"{env_var} must be an integer, got {raw!r}") from exc

    @staticmethod
    def _read_bool(env_var: str) -> bool:
        return os.environ.get(env_var, "").strip().lower() in ("1", "true", "yes")
