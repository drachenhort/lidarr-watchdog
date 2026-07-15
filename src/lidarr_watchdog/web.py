from __future__ import annotations

import sqlite3
from pathlib import Path

import requests
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from lidarr_watchdog import history, settings

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


def create_app(conn: sqlite3.Connection) -> FastAPI:
    app = FastAPI(title="lidarr-watchdog")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "last_check": history.get_last_check(conn),
                "events": history.get_recent_events(conn),
                "poll_interval": settings.get_poll_interval(conn),
                "configured": bool(
                    settings.get_lidarr_url(conn) and settings.get_lidarr_api_key(conn)
                ),
            },
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request, saved: bool = False) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "lidarr_url": settings.get_lidarr_url(conn) or "",
                "poll_interval": settings.get_poll_interval(conn),
                "has_api_key": bool(settings.get_lidarr_api_key(conn)),
                "deny_archives": settings.get_deny_archives(conn),
                "deny_executables": settings.get_deny_executables(conn),
                "saved": saved,
                "test_result": None,
            },
        )

    @app.post("/settings", response_class=HTMLResponse)
    def save_settings(
        request: Request,
        lidarr_url: str = Form(...),
        api_key: str = Form(""),
        poll_interval: int = Form(...),
        deny_archives: str | None = Form(None),
        deny_executables: str | None = Form(None),
    ):
        lidarr_url = lidarr_url.strip()
        error = None
        if not lidarr_url.startswith(("http://", "https://")):
            error = "Lidarr URL must start with http:// or https://"
        elif not api_key.strip() and not settings.get_lidarr_api_key(conn):
            error = "API key is required (it wasn't saved by Test connection — enter it here too)"
        elif poll_interval < 10:
            error = "Poll interval must be at least 10 seconds"

        if error:
            return templates.TemplateResponse(
                request,
                "settings.html",
                {
                    "lidarr_url": lidarr_url,
                    "poll_interval": poll_interval,
                    "has_api_key": bool(settings.get_lidarr_api_key(conn)),
                    "deny_archives": deny_archives is not None,
                    "deny_executables": deny_executables is not None,
                    "saved": False,
                    "test_result": f"error: {error}",
                },
                status_code=400,
            )

        settings.set(conn, "lidarr_url", lidarr_url.rstrip("/"))
        if api_key.strip():
            settings.set(conn, "lidarr_api_key", api_key.strip())
        settings.set(conn, "poll_interval", str(poll_interval))
        settings.set_deny_archives(conn, deny_archives is not None)
        settings.set_deny_executables(conn, deny_executables is not None)

        return RedirectResponse(url="/settings?saved=1", status_code=303)

    @app.post("/settings/test", response_class=HTMLResponse)
    def test_settings(
        request: Request,
        lidarr_url: str = Form(...),
        api_key: str = Form(""),
        poll_interval: int = Form(...),
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
                "poll_interval": poll_interval,
                # reflects what's actually persisted, not the key just used for
                # this test — Save is a separate action and may leave the field blank
                "has_api_key": bool(settings.get_lidarr_api_key(conn)),
                "deny_archives": deny_archives is not None,
                "deny_executables": deny_executables is not None,
                "saved": False,
                "test_result": result,
            },
        )

    return app
