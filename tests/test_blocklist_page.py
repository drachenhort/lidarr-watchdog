import responses
from fastapi.testclient import TestClient

from lidarr_watchdog import history, settings
from lidarr_watchdog.web import create_app


def _configure(conn):
    settings.set(conn, "lidarr_url", "http://lidarr.local")
    settings.set(conn, "lidarr_api_key", "key")


def test_blocklist_page_shows_not_configured_message():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.get("/blocklist")

    assert response.status_code == 200
    assert "isn't configured yet" in response.text


@responses.activate
def test_blocklist_page_lists_records():
    conn = history.connect(":memory:")
    _configure(conn)
    responses.add(
        responses.GET,
        "http://lidarr.local/api/v1/blocklist",
        json={
            "page": 1,
            "pageSize": 50,
            "totalRecords": 1,
            "records": [
                {
                    "id": 42,
                    "date": "2026-07-15T04:06:02Z",
                    "sourceTitle": "Some.Album-GROUP",
                    "message": "Manually marked as failed",
                    "artistId": 9,
                    "artist": {"artistName": "Some Artist"},
                }
            ],
        },
        status=200,
    )
    client = TestClient(create_app(conn))

    response = client.get("/blocklist")

    assert response.status_code == 200
    assert "Some Artist" in response.text
    assert "Some.Album-GROUP" in response.text
    assert "Manually marked as failed" in response.text
    assert "2026-07-15 04:06" in response.text


@responses.activate
def test_blocklist_page_shows_empty_state():
    conn = history.connect(":memory:")
    _configure(conn)
    responses.add(
        responses.GET,
        "http://lidarr.local/api/v1/blocklist",
        json={"page": 1, "pageSize": 50, "totalRecords": 0, "records": []},
        status=200,
    )
    client = TestClient(create_app(conn))

    response = client.get("/blocklist")

    assert "Blocklist is empty." in response.text


@responses.activate
def test_blocklist_page_shows_error_when_lidarr_unreachable():
    conn = history.connect(":memory:")
    _configure(conn)
    responses.add(
        responses.GET,
        "http://lidarr.local/api/v1/blocklist",
        status=500,
    )
    client = TestClient(create_app(conn))

    response = client.get("/blocklist")

    assert response.status_code == 200
    assert "banner error" in response.text
    assert "Couldn't reach Lidarr" in response.text


@responses.activate
def test_blocklist_page_computes_pagination():
    conn = history.connect(":memory:")
    _configure(conn)
    responses.add(
        responses.GET,
        "http://lidarr.local/api/v1/blocklist",
        json={
            "page": 1,
            "pageSize": 50,
            "totalRecords": 120,
            "records": [
                {
                    "id": 1,
                    "date": "2026-07-15T04:06:02Z",
                    "sourceTitle": "Some.Album-GROUP",
                    "message": "Manually marked as failed",
                    "artistId": 9,
                    "artist": {"artistName": "Some Artist"},
                }
            ],
        },
        status=200,
    )
    client = TestClient(create_app(conn))

    response = client.get("/blocklist")

    assert "Page 1 of 3" in response.text


@responses.activate
def test_remove_blocklist_entry_calls_lidarr_and_redirects():
    conn = history.connect(":memory:")
    _configure(conn)
    responses.add(
        responses.DELETE,
        "http://lidarr.local/api/v1/blocklist/42",
        status=200,
    )
    client = TestClient(create_app(conn))

    response = client.post(
        "/blocklist/remove", data={"blocklist_id": "42", "page": "2"}, follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/blocklist?page=2"
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == "http://lidarr.local/api/v1/blocklist/42"


def test_remove_blocklist_entry_no_op_when_unconfigured():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.post(
        "/blocklist/remove", data={"blocklist_id": "42", "page": "1"}, follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/blocklist?page=1"


def test_blocklist_requires_auth_when_configured():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, auth_username="admin", auth_password="secret"))

    response = client.get("/blocklist", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
