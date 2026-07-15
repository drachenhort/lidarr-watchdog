from fastapi.testclient import TestClient

from lidarr_watchdog import history
from lidarr_watchdog.web import create_app


def test_healthz():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, poll_interval=300))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_with_no_data():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, poll_interval=300))

    response = client.get("/")

    assert response.status_code == 200
    assert "No checks have run yet." in response.text
    assert "No blocklist events yet." in response.text
    assert "300s" in response.text


def test_dashboard_shows_check_and_events():
    conn = history.connect(":memory:")
    history.record_check(conn, failed_count=1)
    history.record_blocklist_event(conn, queue_id=7, title="Bad Album", messages="import failed")

    client = TestClient(create_app(conn, poll_interval=300))
    response = client.get("/")

    assert response.status_code == 200
    assert "Bad Album" in response.text
    assert "import failed" in response.text
    assert "1 failed import(s) handled" in response.text
