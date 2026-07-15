import responses
from fastapi.testclient import TestClient

from lidarr_watchdog import history, settings
from lidarr_watchdog.web import create_app, format_event_time, format_short_message, get_app_version


def test_format_event_time_strips_seconds_and_offset():
    assert format_event_time("2026-07-15T06:44:48.532920+00:00") == "2026-07-15 06:44"


def test_format_event_time_falls_back_on_unparseable_input():
    assert format_event_time("not-a-timestamp") == "not-a-timestamp"


def test_format_short_message_strips_percentage_detail():
    full = "Album match is not close enough: 27.6 % vs 80 % [artist, album, tracks]"
    assert format_short_message(full) == "Album match is not close enough"


def test_format_short_message_strips_bracket_and_trailing_preposition():
    full = "Couldn't find similar album for [/download/completed/Some.Album]"
    assert format_short_message(full) == "Couldn't find similar album"


def test_format_short_message_leaves_already_short_message_alone():
    assert format_short_message("Has missing tracks") == "Has missing tracks"
    assert format_short_message("Has unmatched tracks") == "Has unmatched tracks"


def test_format_short_message_handles_multiple_joined_reasons():
    full = "Has missing tracks; Worst track match: 22.0 % vs 60 % [track title, recording id]"
    assert format_short_message(full) == "Has missing tracks; Worst track match"


def test_format_short_message_truncates_long_messages():
    full = "Failed to import track, Destination already exists on the filesystem somewhere deep"
    short = format_short_message(full)
    assert short.endswith("…")
    assert len(short) <= 60


def test_get_app_version_returns_non_empty_string():
    assert isinstance(get_app_version(), str)
    assert get_app_version()


def test_dashboard_shows_app_version():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.get("/")

    assert f"v{get_app_version()}" in response.text


def test_healthz():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_with_no_data():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.get("/")

    assert response.status_code == 200
    assert "isn't configured yet" in response.text
    assert "No blocklist events yet." in response.text
    assert "5 minutes" in response.text


def test_dashboard_shows_check_and_events():
    conn = history.connect(":memory:")
    settings.set(conn, "lidarr_url", "http://localhost:8686")
    settings.set(conn, "lidarr_api_key", "secret")
    history.record_check(conn, failed_count=1)
    history.record_blocklist_event(conn, queue_id=7, title="Bad Album", messages="import failed")

    client = TestClient(create_app(conn))
    response = client.get("/")

    assert response.status_code == 200
    assert "Bad Album" in response.text
    assert "import failed" in response.text
    assert "1 failed import(s) handled" in response.text
    assert "isn't configured" not in response.text
    assert "Run now" in response.text

    event = history.get_recent_events(conn)[0]
    assert format_event_time(event["occurred_at"]) in response.text
    assert event["occurred_at"] not in response.text  # raw ISO timestamp not shown

    last_check = history.get_last_check(conn)
    assert format_event_time(last_check["checked_at"]) in response.text
    assert last_check["checked_at"] not in response.text  # raw ISO timestamp not shown


def test_dashboard_shows_blocklist_only_and_ignore_sections():
    conn = history.connect(":memory:")
    settings.set(conn, "lidarr_url", "http://localhost:8686")
    settings.set(conn, "lidarr_api_key", "secret")

    client = TestClient(create_app(conn))
    empty_response = client.get("/")
    assert "No blocklist-only events yet." in empty_response.text
    assert "No ignored albums yet." in empty_response.text

    history.record_blocklist_only_event(
        conn, queue_id=1, album_id=10, title="Repeat Offender", messages="Has missing tracks"
    )
    history.record_ignore_event(
        conn,
        queue_id=2,
        album_id=20,
        artist_id=5,
        title="Always An Archive",
        messages="Archive file detected",
    )

    response = client.get("/")
    assert "Repeat Offender" in response.text
    assert "Always An Archive" in response.text
    assert "No blocklist-only events yet." not in response.text
    assert "No ignored albums yet." not in response.text


def test_dashboard_shows_full_message_as_hover_tooltip():
    conn = history.connect(":memory:")
    settings.set(conn, "lidarr_url", "http://localhost:8686")
    settings.set(conn, "lidarr_api_key", "secret")
    full_message = "Album match is not close enough: 27.6 % vs 80 % [artist, album, tracks]"
    history.record_blocklist_event(conn, queue_id=7, title="Bad Album", messages=full_message)

    client = TestClient(create_app(conn))
    response = client.get("/")

    assert format_short_message(full_message) in response.text
    assert f'title="{full_message}"' in response.text


def test_dashboard_hides_run_now_when_unconfigured():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.get("/")

    assert "Run now" not in response.text


def test_dashboard_shows_check_complete_banner_after_run():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.get("/", params={"ran": "1"})

    assert "Check complete." in response.text


@responses.activate
def test_run_now_triggers_check_and_redirects():
    responses.add(
        responses.GET,
        "http://lidarr:8686/api/v1/queue",
        json={"page": 1, "pageSize": 200, "totalRecords": 0, "records": []},
        status=200,
    )
    conn = history.connect(":memory:")
    settings.set(conn, "lidarr_url", "http://lidarr:8686")
    settings.set(conn, "lidarr_api_key", "secret")
    client = TestClient(create_app(conn))

    response = client.post("/run-now", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/?ran=1"
    last_check = history.get_last_check(conn)
    assert last_check is not None
    assert last_check["error"] is None


def test_settings_page_defaults():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.get("/settings")

    assert response.status_code == 200
    assert 'placeholder="http://localhost:8686"' in response.text
    assert "Lidarr API key" in response.text  # empty-state placeholder, not "unchanged"
    assert 'value="5"' in response.text  # default 300s displayed as 5 minutes
    assert "selected" in response.text
    assert f'value="{settings.DEFAULT_REPEAT_THRESHOLD}"' in response.text


def test_settings_page_masks_existing_api_key():
    conn = history.connect(":memory:")
    settings.set(conn, "lidarr_url", "http://lidarr:8686")
    settings.set(conn, "lidarr_api_key", "super-secret-value")

    client = TestClient(create_app(conn))
    response = client.get("/settings")

    assert "super-secret-value" not in response.text
    assert "unchanged" in response.text


def test_save_settings_persists_and_redirects():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.post(
        "/settings",
        data={
            "lidarr_url": "http://lidarr:8686/",
            "api_key": "my-key",
            "poll_interval_value": "2",
            "poll_interval_unit": "minutes",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/settings?saved=1"
    assert settings.get_lidarr_url(conn) == "http://lidarr:8686"
    assert settings.get_lidarr_api_key(conn) == "my-key"
    assert settings.get_poll_interval(conn) == 120
    assert settings.get_deny_archives(conn) is False
    assert settings.get_repeat_threshold(conn) == settings.DEFAULT_REPEAT_THRESHOLD


def test_save_settings_persists_custom_repeat_threshold():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    client.post(
        "/settings",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "key",
            "poll_interval_value": "300",
            "poll_interval_unit": "seconds",
            "repeat_threshold": "5",
        },
        follow_redirects=False,
    )

    assert settings.get_repeat_threshold(conn) == 5


def test_save_settings_rejects_repeat_threshold_below_one():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.post(
        "/settings",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "key",
            "poll_interval_value": "300",
            "poll_interval_unit": "seconds",
            "repeat_threshold": "0",
        },
    )

    assert response.status_code == 400
    assert "Repeat threshold must be at least 1" in response.text


def test_save_settings_supports_days_and_hours():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    client.post(
        "/settings",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "key",
            "poll_interval_value": "2",
            "poll_interval_unit": "hours",
        },
        follow_redirects=False,
    )
    assert settings.get_poll_interval(conn) == 7200

    client.post(
        "/settings",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "key",
            "poll_interval_value": "1",
            "poll_interval_unit": "days",
        },
        follow_redirects=False,
    )
    assert settings.get_poll_interval(conn) == 86400


def test_save_settings_blank_api_key_keeps_existing():
    conn = history.connect(":memory:")
    settings.set(conn, "lidarr_api_key", "original-key")
    client = TestClient(create_app(conn))

    client.post(
        "/settings",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "",
            "poll_interval_value": "300",
            "poll_interval_unit": "seconds",
        },
        follow_redirects=False,
    )

    assert settings.get_lidarr_api_key(conn) == "original-key"


def test_save_settings_enables_deny_archives_checkbox():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    client.post(
        "/settings",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "key",
            "poll_interval_value": "300",
            "poll_interval_unit": "seconds",
            "deny_archives": "on",
        },
        follow_redirects=False,
    )

    assert settings.get_deny_archives(conn) is True


def test_save_settings_enables_deny_executables_checkbox():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    client.post(
        "/settings",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "key",
            "poll_interval_value": "300",
            "poll_interval_unit": "seconds",
            "deny_executables": "on",
        },
        follow_redirects=False,
    )

    assert settings.get_deny_executables(conn) is True
    assert settings.get_deny_archives(conn) is False


def test_save_settings_rejects_bad_url():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.post(
        "/settings",
        data={
            "lidarr_url": "not-a-url",
            "api_key": "key",
            "poll_interval_value": "300",
            "poll_interval_unit": "seconds",
        },
    )

    assert response.status_code == 400
    assert "must start with http" in response.text
    assert settings.get_lidarr_url(conn) is None


def test_save_settings_rejects_too_short_poll_interval():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.post(
        "/settings",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "key",
            "poll_interval_value": "5",
            "poll_interval_unit": "seconds",
        },
    )

    assert response.status_code == 400
    assert "at least 10 seconds" in response.text


def test_save_settings_rejects_invalid_unit():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.post(
        "/settings",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "key",
            "poll_interval_value": "5",
            "poll_interval_unit": "fortnights",
        },
    )

    assert response.status_code == 400
    assert "Invalid check interval unit" in response.text


def test_save_settings_rejects_missing_api_key_on_first_save():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.post(
        "/settings",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "",
            "poll_interval_value": "300",
            "poll_interval_unit": "seconds",
        },
    )

    assert response.status_code == 400
    assert "API key is required" in response.text
    assert settings.get_lidarr_url(conn) is None


def test_save_settings_blank_api_key_allowed_when_already_saved():
    conn = history.connect(":memory:")
    settings.set(conn, "lidarr_api_key", "existing-key")
    client = TestClient(create_app(conn))

    response = client.post(
        "/settings",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "",
            "poll_interval_value": "300",
            "poll_interval_unit": "seconds",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert settings.get_lidarr_api_key(conn) == "existing-key"


@responses.activate
def test_test_connection_success():
    responses.add(
        responses.GET,
        "http://lidarr:8686/api/v1/system/status",
        json={"version": "2.5.0"},
        status=200,
    )
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.post(
        "/settings/test",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "key",
            "poll_interval_value": "300",
            "poll_interval_unit": "seconds",
        },
    )

    assert response.status_code == 200
    assert "connected to Lidarr 2.5.0" in response.text
    # test-connection must not persist anything
    assert settings.get_lidarr_url(conn) is None
    # the typed-but-unsaved key must not be presented as "already saved"
    assert "unchanged" not in response.text


@responses.activate
def test_test_connection_failure():
    responses.add(
        responses.GET,
        "http://lidarr:8686/api/v1/system/status",
        status=401,
    )
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.post(
        "/settings/test",
        data={
            "lidarr_url": "http://lidarr:8686",
            "api_key": "bad-key",
            "poll_interval_value": "300",
            "poll_interval_unit": "seconds",
        },
    )

    assert response.status_code == 200
    assert "banner error" in response.text
