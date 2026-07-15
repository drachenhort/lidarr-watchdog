import base64

from fastapi.testclient import TestClient

from lidarr_watchdog import history
from lidarr_watchdog.web import check_basic_auth, create_app, is_local_address


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


def test_is_local_address_true_for_private_ranges():
    assert is_local_address("127.0.0.1") is True
    assert is_local_address("192.168.1.5") is True
    assert is_local_address("10.0.0.1") is True
    assert is_local_address("172.16.5.5") is True
    assert is_local_address("::1") is True
    assert is_local_address("fe80::1") is True


def test_is_local_address_false_for_public_or_invalid():
    assert is_local_address("8.8.8.8") is False
    assert is_local_address("172.32.5.5") is False  # just outside 172.16.0.0/12
    assert is_local_address(None) is False
    assert is_local_address("") is False
    assert is_local_address("not-an-ip") is False


def test_skip_auth_for_local_bypasses_auth_for_private_client_ip():
    conn = history.connect(":memory:")
    app = create_app(
        conn, auth_username="admin", auth_password="secret", skip_auth_for_local=True
    )
    client = TestClient(app, client=("192.168.1.50", 12345))

    response = client.get("/")

    assert response.status_code == 200


def test_skip_auth_for_local_still_requires_auth_for_public_client_ip():
    conn = history.connect(":memory:")
    app = create_app(
        conn, auth_username="admin", auth_password="secret", skip_auth_for_local=True
    )
    client = TestClient(app, client=("8.8.8.8", 12345))

    response = client.get("/")

    assert response.status_code == 401


def test_skip_auth_for_local_off_by_default_even_for_private_ip():
    conn = history.connect(":memory:")
    app = create_app(conn, auth_username="admin", auth_password="secret")
    client = TestClient(app, client=("192.168.1.50", 12345))

    response = client.get("/")

    assert response.status_code == 401


def test_login_page_not_found_when_auth_not_configured():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn))

    assert client.get("/login").status_code == 404


def test_login_page_reachable_without_credentials_when_auth_configured():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, auth_username="admin", auth_password="secret"))

    response = client.get("/login")

    assert response.status_code == 200
    assert "Log in" in response.text


def test_login_page_shows_error_banner():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, auth_username="admin", auth_password="secret"))

    response = client.get("/login", params={"error": "1"})

    assert "Invalid username or password" in response.text


def test_login_submit_wrong_credentials_redirects_with_error_and_no_cookie():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, auth_username="admin", auth_password="secret"))

    response = client.post(
        "/login", data={"username": "admin", "password": "wrong"}, follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=1"
    assert "lw_session" not in response.cookies


def test_login_submit_correct_credentials_sets_cookie_and_grants_access():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, auth_username="admin", auth_password="secret"))

    login_response = client.post(
        "/login", data={"username": "admin", "password": "secret"}, follow_redirects=False
    )
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/"
    assert "lw_session" in login_response.cookies

    # TestClient persists cookies across requests on the same client, so a
    # follow-up request with no Basic Auth header should now succeed purely
    # on the session cookie set by the login form.
    dashboard_response = client.get("/")
    assert dashboard_response.status_code == 200
    assert "Log out" in dashboard_response.text


def test_logout_clears_cookie_and_revokes_access():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, auth_username="admin", auth_password="secret"))

    client.post("/login", data={"username": "admin", "password": "secret"})
    assert client.get("/").status_code == 200

    logout_response = client.post("/logout", follow_redirects=False)
    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/login"

    assert client.get("/").status_code == 401


def test_basic_auth_still_works_independently_of_session_cookie():
    conn = history.connect(":memory:")
    client = TestClient(create_app(conn, auth_username="admin", auth_password="secret"))

    # Never visited /login, no cookie at all — Basic Auth header alone
    # must still work, unaffected by the new login-form code path.
    response = client.get("/", auth=("admin", "secret"))

    assert response.status_code == 200
