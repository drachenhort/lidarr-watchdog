# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

lidarr-watchdog polls a Lidarr instance's download queue and blocklists
items whose import actually failed (`trackedDownloadState == "importFailed"`),
letting Lidarr auto-search for a replacement. It can optionally also deny
queue items that are archives or executables. A FastAPI dashboard shows
check/blocklist history and a Settings page for runtime config. Everything
(Lidarr URL/API key, poll interval, deny toggles, repeat threshold) is
stored in SQLite and editable live — no restart required. See README.md
for full behavior (auth model, repeat-escalation rules, Docker/PUID setup).

## Commands

```sh
python3 -m venv .venv && .venv/bin/pip install -e . pytest responses httpx2
.venv/bin/pytest                          # run full test suite
.venv/bin/pytest tests/test_watchdog.py   # single file
.venv/bin/pytest tests/test_watchdog.py::test_check_once_blocklists_and_requeues_failed_imports  # single test
.venv/bin/lidarr-watchdog                 # run the app (serves on :8000)
```

`uv run pytest` / `uv run lidarr-watchdog` work equivalently if using uv.

CI (`.github/workflows/tests.yml`) runs pytest on Python 3.11/3.12/3.13 on
every push/PR. There is no linter/formatter configured in this repo.

Versions come from git tags via `hatch-vcs` (`vX.Y.Z`) — never hardcode a
version. Add unreleased changes under `[Unreleased]` in `CHANGELOG.md`.

## Architecture

Layered, single-process app: a background poll thread and a FastAPI web
server share one `sqlite3.Connection` (`check_same_thread=False`, WAL
mode, a module-level `threading.Lock` around every read/write in
`history.py`/`settings.py` to serialize access from both threads).

Call chain for a poll cycle: `main._run_watchdog_loop` (thread loop, sleeps
`settings.get_poll_interval()` between cycles) → `checker.run_check_cycle`
→ `checker.check_and_record` → `watchdog.check_once` (pure queue-scan/deny
logic, framework-free) → callbacks back into `checker._on_deny` /
`checker._resolve_skip_redownload` which apply repeat-count/escalation
policy and write history rows.

- **`watchdog.py`** — pure classification/deny logic (`is_failed_import`,
  `is_archive`, `is_executable`, `check_once`). No DB or settings access;
  takes plain dicts (raw Lidarr queue records) and callbacks. This is the
  layer to test queue-decision logic against without touching SQLite.
- **`checker.py`** — orchestration: resolves/caches a `LidarrClient` per
  connection (keyed by `id(conn)`, invalidated on URL/API-key change),
  wires `watchdog.check_once`'s callbacks to repeat-count tracking and
  history writes, and is what `main.py` and `web.py` (`/run-now`) both
  call to actually run a cycle.
- **`lidarr_client.py`** — thin wrapper over Lidarr's REST API
  (`/api/v1/queue`, `/blocklist`, `/album/{id}`). No retry/backoff; raises
  on HTTP errors via `raise_for_status()`.
- **`settings.py`** — key/value store in the `settings` SQLite table.
  Every setting has a `get_x`/`set_x` pair here; this is the single source
  of truth for runtime config (env vars only *seed* these on first run,
  see `main.main()`).
- **`history.py`** — event-log tables (`checks`, `blocklist_events`,
  `blocklist_only_events`, `ignore_events`, `repeat_counts`), each pruned
  to a row cap (`_MAX_CHECK_ROWS`/`_MAX_EVENT_ROWS`) on every insert so
  long-running deployments don't grow the DB unbounded.
- **`web.py`** — FastAPI app: dashboard, Settings, Blocklist pages, and
  the auth middleware. Routes read/write through `settings.py`/`history.py`
  only — no direct SQL here.
- **`config.py`** — env-var parsing into a frozen `Config` dataclass,
  consumed once in `main.main()` to seed SQLite and to configure
  host/port/auth (auth credentials are env-only, never editable via
  Settings — see below).

### Repeat escalation (the non-obvious business rule)

Failed-import and archive/executable-denial counts are tracked
*independently* per album (`repeat_counts` table, keyed by
`(album_id, reason)` where `reason` collapses to `"failed_import"` or
`"denied"` via `checker._category`). Once a category's count reaches the
configured "Repeat threshold" (default 3) for an album:

- Repeated **failed imports** → blocklist without re-triggering a search
  (`skip_redownload=True`); album stays monitored. Logged to
  `blocklist_only_events`.
- Repeated **archive/executable denials** → Lidarr is told to unmonitor
  the album entirely (`LidarrClient.unmonitor_album`) since re-searching
  keeps finding the same undesirable files. Logged to `ignore_events`.

Below threshold, both paths just log to `blocklist_events` as normal.
`checker._resolve_skip_redownload` runs (and increments the count) before
`_on_deny` is called for the same record, and caches the count in a
per-cycle `repeat_counts` dict so `_on_deny` doesn't re-read the DB or
depend on call order.

### Auth model

No auth by default. Setting both `LIDARR_WATCHDOG_USERNAME` and
`LIDARR_WATCHDOG_PASSWORD` env vars (only) enables it — these are
intentionally *not* editable from the Settings page, so a compromised
session can't disable auth on itself. When enabled:

- A credential-less browser request is redirected to `/login` (HTML form,
  not the native Basic Auth popup); `/healthz`, `/login`, `/logout` are
  always exempt.
- An explicit `Authorization: Basic` header (curl, scripts) is still
  honored directly by the same middleware.
- Session cookie's signing value (`session_token`) is a random value
  regenerated in memory per process start and rotated on logout — never
  persisted, so all sessions invalidate on restart.
- "Skip login for local network" only trusts `request.client.host` (the
  direct TCP peer), never `X-Forwarded-For` — deliberately not
  proxy-aware; leave it off behind a reverse proxy.

### Templates

Server-rendered Jinja2 (`templates/*.html`, `base.html` for shared chrome),
no frontend build step/JS framework. Custom Jinja filters
(`event_time`, `short_message`) are registered in `web.create_app`.

## Testing conventions

Tests mirror source modules 1:1 (`test_watchdog.py`, `test_checker.py`,
etc.) plus `test_auth.py`/`test_web.py`/`test_blocklist_page.py` for HTTP
routes via FastAPI's `TestClient`. `responses` mocks outbound Lidarr HTTP
calls; tests generally build a fresh in-memory/temp SQLite DB per test via
`history.connect(":memory:")` or a tmp path rather than mocking the DB
layer.
