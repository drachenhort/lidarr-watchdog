import pytest

from lidarr_watchdog.config import Config, ConfigError


def test_from_env_reads_required_values(monkeypatch):
    monkeypatch.setenv("LIDARR_URL", "http://localhost:8686/")
    monkeypatch.setenv("LIDARR_API_KEY", "secret")
    monkeypatch.delenv("LIDARR_WATCHDOG_POLL_INTERVAL", raising=False)

    config = Config.from_env()

    assert config.lidarr_url == "http://localhost:8686"
    assert config.api_key == "secret"
    assert config.poll_interval == 300


def test_from_env_reads_custom_poll_interval(monkeypatch):
    monkeypatch.setenv("LIDARR_URL", "http://localhost:8686")
    monkeypatch.setenv("LIDARR_API_KEY", "secret")
    monkeypatch.setenv("LIDARR_WATCHDOG_POLL_INTERVAL", "60")

    config = Config.from_env()

    assert config.poll_interval == 60


def test_from_env_requires_url(monkeypatch):
    monkeypatch.delenv("LIDARR_URL", raising=False)
    monkeypatch.setenv("LIDARR_API_KEY", "secret")

    with pytest.raises(ConfigError, match="LIDARR_URL"):
        Config.from_env()


def test_from_env_requires_api_key(monkeypatch):
    monkeypatch.setenv("LIDARR_URL", "http://localhost:8686")
    monkeypatch.delenv("LIDARR_API_KEY", raising=False)

    with pytest.raises(ConfigError, match="LIDARR_API_KEY"):
        Config.from_env()


def test_from_env_rejects_non_integer_poll_interval(monkeypatch):
    monkeypatch.setenv("LIDARR_URL", "http://localhost:8686")
    monkeypatch.setenv("LIDARR_API_KEY", "secret")
    monkeypatch.setenv("LIDARR_WATCHDOG_POLL_INTERVAL", "soon")

    with pytest.raises(ConfigError, match="LIDARR_WATCHDOG_POLL_INTERVAL"):
        Config.from_env()
