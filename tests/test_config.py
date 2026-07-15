import pytest

from lidarr_watchdog.config import Config, ConfigError


def test_from_env_defaults_with_nothing_set(monkeypatch):
    monkeypatch.delenv("LIDARR_URL", raising=False)
    monkeypatch.delenv("LIDARR_API_KEY", raising=False)
    monkeypatch.delenv("LIDARR_WATCHDOG_POLL_INTERVAL", raising=False)
    monkeypatch.delenv("LIDARR_WATCHDOG_HOST", raising=False)
    monkeypatch.delenv("LIDARR_WATCHDOG_PORT", raising=False)
    monkeypatch.delenv("LIDARR_WATCHDOG_DB_PATH", raising=False)
    monkeypatch.delenv("LIDARR_WATCHDOG_USERNAME", raising=False)
    monkeypatch.delenv("LIDARR_WATCHDOG_PASSWORD", raising=False)
    monkeypatch.delenv("LIDARR_WATCHDOG_SKIP_AUTH_FOR_LOCAL", raising=False)

    config = Config.from_env()

    assert config.seed_lidarr_url is None
    assert config.seed_lidarr_api_key is None
    assert config.seed_poll_interval is None
    assert config.host == "0.0.0.0"
    assert config.port == 8000
    assert config.db_path == "lidarr-watchdog.db"
    assert config.auth_username is None
    assert config.auth_password is None
    assert config.skip_auth_for_local is False


def test_from_env_reads_auth_settings(monkeypatch):
    monkeypatch.setenv("LIDARR_WATCHDOG_USERNAME", "admin")
    monkeypatch.setenv("LIDARR_WATCHDOG_PASSWORD", "secret")
    monkeypatch.setenv("LIDARR_WATCHDOG_SKIP_AUTH_FOR_LOCAL", "true")

    config = Config.from_env()

    assert config.auth_username == "admin"
    assert config.auth_password == "secret"
    assert config.skip_auth_for_local is True


def test_from_env_skip_auth_for_local_accepts_common_truthy_values(monkeypatch):
    for value in ("1", "true", "True", "yes", "YES"):
        monkeypatch.setenv("LIDARR_WATCHDOG_SKIP_AUTH_FOR_LOCAL", value)
        assert Config.from_env().skip_auth_for_local is True

    for value in ("0", "false", "no", ""):
        monkeypatch.setenv("LIDARR_WATCHDOG_SKIP_AUTH_FOR_LOCAL", value)
        assert Config.from_env().skip_auth_for_local is False


def test_from_env_reads_seed_values(monkeypatch):
    monkeypatch.setenv("LIDARR_URL", "http://localhost:8686/")
    monkeypatch.setenv("LIDARR_API_KEY", "secret")
    monkeypatch.setenv("LIDARR_WATCHDOG_POLL_INTERVAL", "60")

    config = Config.from_env()

    assert config.seed_lidarr_url == "http://localhost:8686"
    assert config.seed_lidarr_api_key == "secret"
    assert config.seed_poll_interval == 60


def test_from_env_rejects_non_integer_poll_interval(monkeypatch):
    monkeypatch.setenv("LIDARR_WATCHDOG_POLL_INTERVAL", "soon")

    with pytest.raises(ConfigError, match="LIDARR_WATCHDOG_POLL_INTERVAL"):
        Config.from_env()


def test_from_env_rejects_non_integer_port(monkeypatch):
    monkeypatch.setenv("LIDARR_WATCHDOG_PORT", "soon")

    with pytest.raises(ConfigError, match="LIDARR_WATCHDOG_PORT"):
        Config.from_env()
