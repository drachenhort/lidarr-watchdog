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


def test_deny_executables_defaults_false():
    conn = history.connect(":memory:")
    assert settings.get_deny_executables(conn) is False


def test_deny_executables_roundtrip():
    conn = history.connect(":memory:")
    settings.set_deny_executables(conn, True)
    assert settings.get_deny_executables(conn) is True

    settings.set_deny_executables(conn, False)
    assert settings.get_deny_executables(conn) is False


def test_split_poll_interval_picks_largest_clean_unit():
    assert settings.split_poll_interval(30) == (30, "seconds")
    assert settings.split_poll_interval(300) == (5, "minutes")
    assert settings.split_poll_interval(7200) == (2, "hours")
    assert settings.split_poll_interval(86400) == (1, "days")
    assert settings.split_poll_interval(90) == (90, "seconds")  # not clean minutes


def test_split_poll_interval_prefers_larger_units_when_multiple_fit():
    # 3600s divides evenly by both minutes (60) and hours (1) - hours should win
    assert settings.split_poll_interval(3600) == (1, "hours")


def test_format_poll_interval_pluralizes():
    assert settings.format_poll_interval(300) == "5 minutes"
    assert settings.format_poll_interval(60) == "1 minute"
    assert settings.format_poll_interval(30) == "30 seconds"
    assert settings.format_poll_interval(1) == "1 second"


def test_get_repeat_threshold_defaults_when_unset():
    conn = history.connect(":memory:")
    assert settings.get_repeat_threshold(conn) == settings.DEFAULT_REPEAT_THRESHOLD


def test_repeat_threshold_roundtrip():
    conn = history.connect(":memory:")
    settings.set_repeat_threshold(conn, 5)
    assert settings.get_repeat_threshold(conn) == 5
