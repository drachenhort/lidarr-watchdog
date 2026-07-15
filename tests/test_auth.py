import base64

from fastapi.testclient import TestClient

from lidarr_watchdog import history
from lidarr_watchdog.web import check_basic_auth, create_app


def _basic_header(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    # lowercase key: real Starlette Request.headers is case-insensitive, but
    # this fake is a plain dict, so it must match what check_basic_auth looks up
    return {"authorization": f"Basic {token}"}


class _FakeRequest:
    def __init__(self, headers: dict[str, str]):
        self.headers = headers


def test_check_basic_auth_accepts_correct_credentials():
    request = _FakeRequest(_basic_header("admin", "secret"))
    assert check_basic_auth(request, "admin", "secret") is True


def test_check_basic_auth_rejects_wrong_password():
    request = _FakeRequest(_basic_header("admin", "wrong"))
    assert check_basic_auth(request, "admin", "secret") is False


def test_check_basic_auth_rejects_wrong_username():
    request = _FakeRequest(_basic_header("someone-else", "secret"))
    assert check_basic_auth(request, "admin", "secret") is False


def test_check_basic_auth_rejects_missing_header():
    request = _FakeRequest({})
    assert check_basic_auth(request, "admin", "secret") is False


def test_check_basic_auth_rejects_non_basic_scheme():
    request = _FakeRequest({"authorization": "Bearer sometoken"})
    assert check_basic_auth(request, "admin", "secret") is False


def test_check_basic_auth_rejects_malformed_base64():
    request = _FakeRequest({"authorization": "Basic not-valid-base64!!!"})
    assert check_basic_auth(request, "admin", "secret") is False


def test_no_auth_configured_allows_unauthenticated_access():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    response = client.get("/")

    assert response.status_code == 200


def test_auth_configured_rejects_unauthenticated_dashboard():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, auth_username="admin", auth_password="secret"))

    response = client.get("/")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="lidarr-watchdog"'


def test_auth_configured_accepts_correct_credentials():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, auth_username="admin", auth_password="secret"))

    response = client.get("/", auth=("admin", "secret"))

    assert response.status_code == 200


def test_auth_configured_rejects_wrong_credentials():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, auth_username="admin", auth_password="secret"))

    response = client.get("/", auth=("admin", "wrong-password"))

    assert response.status_code == 401


def test_auth_configured_protects_settings_and_run_now():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, auth_username="admin", auth_password="secret"))

    assert client.get("/settings").status_code == 401
    assert client.post("/run-now").status_code == 401

    assert client.get("/settings", auth=("admin", "secret")).status_code == 200


def test_auth_configured_exempts_healthz():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, auth_username="admin", auth_password="secret"))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
