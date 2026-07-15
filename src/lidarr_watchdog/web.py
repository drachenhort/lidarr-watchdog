from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from lidarr_watchdog import history

TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(conn: sqlite3.Connection, poll_interval: int) -> FastAPI:
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
                "poll_interval": poll_interval,
            },
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
