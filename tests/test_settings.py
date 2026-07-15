from lidarr_watchdog import history, settings


def test_get_returns_none_when_unset():
    conn = history.connect(":memory:")
    assert settings.get(conn, "lidarr_url") is None


def test_set_and_get_roundtrip():
    conn = history.connect(":memory:")
    settings.set(conn, "lidarr_url", "http://localhost:8686")
    assert settings.get(conn, "lidarr_url") == "http://localhost:8686"


def test_set_overwrites_existing_value():
    conn = history.connect(":memory:")
    settings.set(conn, "lidarr_url", "http://old:8686")
    settings.set(conn, "lidarr_url", "http://new:8686")
    assert settings.get(conn, "lidarr_url") == "http://new:8686"


def test_seed_if_unset_only_seeds_once():
    conn = history.connect(":memory:")
    settings.seed_if_unset(conn, "lidarr_url", "http://seed:8686")
    assert settings.get(conn, "lidarr_url") == "http://seed:8686"

    settings.seed_if_unset(conn, "lidarr_url", "http://other-seed:8686")
    assert settings.get(conn, "lidarr_url") == "http://seed:8686"


def test_seed_if_unset_ignores_none_value():
    conn = history.connect(":memory:")
    settings.seed_if_unset(conn, "lidarr_url", None)
    assert settings.get(conn, "lidarr_url") is None


def test_get_poll_interval_defaults_when_unset():
    conn = history.connect(":memory:")
    assert settings.get_poll_interval(conn) == settings.DEFAULT_POLL_INTERVAL


def test_get_poll_interval_reads_stored_value():
    conn = history.connect(":memory:")
    settings.set(conn, "poll_interval", "60")
    assert settings.get_poll_interval(conn) == 60


def test_deny_archives_defaults_false():
    conn = history.connect(":memory:")
    assert settings.get_deny_archives(conn) is False


def test_deny_archives_roundtrip():
    conn = history.connect(":memory:")
    settings.set_deny_archives(conn, True)
    assert settings.get_deny_archives(conn) is True

    settings.set_deny_archives(conn, False)
    assert settings.get_deny_archives(conn) is False
