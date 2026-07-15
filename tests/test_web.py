import responses
from fastapi.testclient import TestClient

from lidarr_watchdog import history, settings
from lidarr_watchdog.web import create_app


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
    assert "300s" in response.text


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


def test_settings_page_defaults():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.get("/settings")

    assert response.status_code == 200
    assert 'placeholder="http://localhost:8686"' in response.text
    assert "Lidarr API key" in response.text  # empty-state placeholder, not "unchanged"


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
        data={"lidarr_url": "http://lidarr:8686/", "api_key": "my-key", "poll_interval": "120"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/settings?saved=1"
    assert settings.get_lidarr_url(conn) == "http://lidarr:8686"
    assert settings.get_lidarr_api_key(conn) == "my-key"
    assert settings.get_poll_interval(conn) == 120
    assert settings.get_deny_archives(conn) is False


def test_save_settings_blank_api_key_keeps_existing():
    conn = history.connect(":memory:")
    settings.set(conn, "lidarr_api_key", "original-key")
    client = TestClient(create_app(conn))

    client.post(
        "/settings",
        data={"lidarr_url": "http://lidarr:8686", "api_key": "", "poll_interval": "300"},
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
            "poll_interval": "300",
            "deny_archives": "on",
        },
        follow_redirects=False,
    )

    assert settings.get_deny_archives(conn) is True


def test_save_settings_rejects_bad_url():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.post(
        "/settings",
        data={"lidarr_url": "not-a-url", "api_key": "key", "poll_interval": "300"},
    )

    assert response.status_code == 400
    assert "must start with http" in response.text
    assert settings.get_lidarr_url(conn) is None


def test_save_settings_rejects_too_short_poll_interval():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.post(
        "/settings",
        data={"lidarr_url": "http://lidarr:8686", "api_key": "key", "poll_interval": "5"},
    )

    assert response.status_code == 400
    assert "at least 10 seconds" in response.text


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
        data={"lidarr_url": "http://lidarr:8686", "api_key": "key", "poll_interval": "300"},
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
        data={"lidarr_url": "http://lidarr:8686", "api_key": "bad-key", "poll_interval": "300"},
    )

    assert response.status_code == 200
    assert "banner error" in response.text
