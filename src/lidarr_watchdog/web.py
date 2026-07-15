from __future__ import annotations

import base64
import binascii
import ipaddress
import re
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

import requests
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from lidarr_watchdog import history, settings
from lidarr_watchdog.checker import run_check_cycle

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _test_connection(lidarr_url: str, api_key: str) -> str:
    if not lidarr_url:
        return "error: Lidarr URL is required"
    if not api_key:
        return "error: API key is required"
    try:
        response = requests.get(
            f"{lidarr_url.rstrip('/')}/api/v1/system/status",
            headers={"X-Api-Key": api_key},
            timeout=10,
        )
        response.raise_for_status()
        version = response.json().get("version", "unknown")
        return f"ok: connected to Lidarr {version}"
    except requests.RequestException as exc:
        return f"error: {exc}"


def format_event_time(iso_timestamp: str) -> str:
    try:
        return datetime.fromisoformat(iso_timestamp).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_timestamp


_TRAILING_BRACKET_RE = re.compile(r"\s*\[[^\]]*\]\s*$")
_TRAILING_FILLER_RE = re.compile(r"\s+(for|in|at|of|to)$", re.IGNORECASE)
_MAX_SHORT_MESSAGE_LENGTH = 60


def _shorten_single_message(message: str) -> str:
    short = message.split(":", 1)[0].strip()
    short = _TRAILING_BRACKET_RE.sub("", short).strip()
    short = _TRAILING_FILLER_RE.sub("", short).strip()
    if len(short) > _MAX_SHORT_MESSAGE_LENGTH:
        short = short[: _MAX_SHORT_MESSAGE_LENGTH - 1].rstrip() + "…"
    return short or message


def format_short_message(full_message: str) -> str:
    parts = [_shorten_single_message(part) for part in full_message.split("; ") if part]
    return "; ".join(parts) if parts else full_message


def check_basic_auth(request: Request, username: str, password: str) -> bool:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header.removeprefix("Basic "), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    req_username, sep, req_password = decoded.partition(":")
    if not sep:
        return False
    return secrets.compare_digest(req_username, username) and secrets.compare_digest(
        req_password, password
    )


def is_local_address(host: str | None) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


_UNAUTHORIZED = Response(
    status_code=401,
    content="Unauthorized",
    headers={"WWW-Authenticate": 'Basic realm="lidarr-watchdog"'},
)

SESSION_COOKIE_NAME = "lw_session"


def create_app(
    conn: sqlite3.Connection,
    auth_username: str | None = None,
    auth_password: str | None = None,
    skip_auth_for_local: bool = False,
) -> FastAPI:
    app = FastAPI(title="lidarr-watchdog")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.filters["event_time"] = format_event_time
    templates.env.filters["short_message"] = format_short_message

    auth_enabled = bool(auth_username and auth_password)
    # Random per-process value: presenting it back as a cookie proves the
    # browser passed the /login form in *this* run. Restarting the process
    # invalidates all sessions, which is an acceptable tradeoff for not
    # persisting a signing secret anywhere.
    session_token = secrets.token_hex(32) if auth_enabled else None

    if auth_enabled:

        @app.middleware("http")
        async def require_basic_auth(request: Request, call_next):
            if request.url.path in ("/healthz", "/login", "/logout"):
                return await call_next(request)
            # Only the direct TCP peer address is trusted here, never a
            # proxy header like X-Forwarded-For (trivially spoofable by any
            # client unless a specific proxy is trusted and configured to
            # strip/validate it, which this app does not do). Behind a
            # reverse proxy, request.client.host is the proxy's own
            # address, not the original client's — so this bypass should
            # be left off in that setup, or it will treat all proxied
            # traffic as local.
            client_host = request.client.host if request.client else None
            if skip_auth_for_local and is_local_address(client_host):
                return await call_next(request)
            session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
            if session_cookie and secrets.compare_digest(session_cookie, session_token):
                return await call_next(request)
            if check_basic_auth(request, auth_username, auth_password):
                return await call_next(request)
            return _UNAUTHORIZED

        @app.get("/login", response_class=HTMLResponse)
        def login_page(request: Request, error: bool = False) -> HTMLResponse:
            return templates.TemplateResponse(request, "login.html", {"error": error})

        @app.post("/login")
        def login_submit(username: str = Form(...), password: str = Form("")):
            if secrets.compare_digest(username, auth_username) and secrets.compare_digest(
                password, auth_password
            ):
                response = RedirectResponse(url="/", status_code=303)
                response.set_cookie(
                    SESSION_COOKIE_NAME, session_token, httponly=True, samesite="lax"
                )
                return response
            return RedirectResponse(url="/login?error=1", status_code=303)

        @app.post("/logout")
        def logout() -> RedirectResponse:
            response = RedirectResponse(url="/login", status_code=303)
            response.delete_cookie(SESSION_COOKIE_NAME)
            return response

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, ran: bool = False) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "last_check": history.get_last_check(conn),
                "events": history.get_recent_events(conn),
                "poll_interval_display": settings.format_poll_interval(
                    settings.get_poll_interval(conn)
                ),
                "configured": bool(
                    settings.get_lidarr_url(conn) and settings.get_lidarr_api_key(conn)
                ),
                "just_ran": ran,
                "auth_enabled": auth_enabled,
            },
        )

    @app.post("/run-now")
    def run_now() -> RedirectResponse:
        run_check_cycle(conn)
        return RedirectResponse(url="/?ran=1", status_code=303)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request, saved: bool = False) -> HTMLResponse:
        poll_interval_value, poll_interval_unit = settings.split_poll_interval(
            settings.get_poll_interval(conn)
        )
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "lidarr_url": settings.get_lidarr_url(conn) or "",
                "poll_interval_value": poll_interval_value,
                "poll_interval_unit": poll_interval_unit,
                "poll_interval_units": settings.POLL_INTERVAL_UNIT_SECONDS,
                "has_api_key": bool(settings.get_lidarr_api_key(conn)),
                "deny_archives": settings.get_deny_archives(conn),
                "deny_executables": settings.get_deny_executables(conn),
                "saved": saved,
                "test_result": None,
                "auth_enabled": auth_enabled,
            },
        )

    @app.post("/settings", response_class=HTMLResponse)
    def save_settings(
        request: Request,
        lidarr_url: str = Form(...),
        api_key: str = Form(""),
        poll_interval_value: int = Form(...),
        poll_interval_unit: str = Form(...),
        deny_archives: str | None = Form(None),
        deny_executables: str | None = Form(None),
    ):
        lidarr_url = lidarr_url.strip()
        unit_seconds = settings.POLL_INTERVAL_UNIT_SECONDS.get(poll_interval_unit)
        total_seconds = poll_interval_value * unit_seconds if unit_seconds else None

        error = None
        if not lidarr_url.startswith(("http://", "https://")):
            error = "Lidarr URL must start with http:// or https://"
        elif not api_key.strip() and not settings.get_lidarr_api_key(conn):
            error = "API key is required (it wasn't saved by Test connection — enter it here too)"
        elif unit_seconds is None:
            error = "Invalid check interval unit"
        elif total_seconds < 10:
            error = "Check interval must be at least 10 seconds"

        if error:
            return templates.TemplateResponse(
                request,
                "settings.html",
                {
                    "lidarr_url": lidarr_url,
                    "poll_interval_value": poll_interval_value,
                    "poll_interval_unit": poll_interval_unit,
                    "poll_interval_units": settings.POLL_INTERVAL_UNIT_SECONDS,
                    "has_api_key": bool(settings.get_lidarr_api_key(conn)),
                    "deny_archives": deny_archives is not None,
                    "deny_executables": deny_executables is not None,
                    "saved": False,
                    "test_result": f"error: {error}",
                    "auth_enabled": auth_enabled,
                },
                status_code=400,
            )

        settings.set(conn, "lidarr_url", lidarr_url.rstrip("/"))
        if api_key.strip():
            settings.set(conn, "lidarr_api_key", api_key.strip())
        settings.set(conn, "poll_interval", str(total_seconds))
        settings.set_deny_archives(conn, deny_archives is not None)
        settings.set_deny_executables(conn, deny_executables is not None)

        return RedirectResponse(url="/settings?saved=1", status_code=303)

    @app.post("/settings/test", response_class=HTMLResponse)
    def test_settings(
        request: Request,
        lidarr_url: str = Form(...),
        api_key: str = Form(""),
        poll_interval_value: int = Form(...),
        poll_interval_unit: str = Form(...),
        deny_archives: str | None = Form(None),
        deny_executables: str | None = Form(None),
    ) -> HTMLResponse:
        effective_key = api_key.strip() or (settings.get_lidarr_api_key(conn) or "")
        result = _test_connection(lidarr_url.strip(), effective_key)
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "lidarr_url": lidarr_url.strip(),
                "poll_interval_value": poll_interval_value,
                "poll_interval_unit": poll_interval_unit,
                "poll_interval_units": settings.POLL_INTERVAL_UNIT_SECONDS,
                # reflects what's actually persisted, not the key just used for
                # this test — Save is a separate action and may leave the field blank
                "has_api_key": bool(settings.get_lidarr_api_key(conn)),
                "deny_archives": deny_archives is not None,
                "deny_executables": deny_executables is not None,
                "saved": False,
                "test_result": result,
                "auth_enabled": auth_enabled,
            },
        )

    return app
