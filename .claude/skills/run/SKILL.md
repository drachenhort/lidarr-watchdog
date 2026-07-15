---
name: run
description: Launch and drive the lidarr-watchdog app (poller + FastAPI dashboard) for this repo. Use when asked to run, start, or screenshot lidarr-watchdog, or to confirm a change works in the real app.
user-invocable: true
---

# Running lidarr-watchdog

This is a single Python process: a background thread polls Lidarr's queue
on an interval, and a FastAPI dashboard (served via `uvicorn.run`, which
blocks the main thread) shows the check/blocklist history from a SQLite
file. There are two ways to run it, depending on whether a real Lidarr
instance is available.

## Setup (once per checkout)

```sh
python3 -m venv .venv
.venv/bin/pip install -e . pytest responses httpx2
```

Lidarr connection (URL, API key), the poll interval, and the "deny
archives" toggle are all runtime settings stored in the `settings` SQLite
table (see `settings.py`), editable live from the `/settings` page —
`LIDARR_URL`/`LIDARR_API_KEY`/`LIDARR_WATCHDOG_POLL_INTERVAL` env vars only
*seed* those values on first run (`Config.from_env()` + `seed_if_unset`);
they don't override a value already saved via the UI. Nothing is required
to start the process — with no Lidarr configured yet, `main.py` still
serves the dashboard and settings page, it just records a "not configured"
check each poll cycle instead of hitting Lidarr.

## Option A — no real Lidarr instance (dashboard-only, for UI/template work)

Seed the SQLite history directly and serve the FastAPI app on its own,
bypassing the poll loop entirely:

```sh
.venv/bin/python .claude/skills/run/scripts/serve_demo.py /tmp/lidarr-watchdog-demo.db 8765 &
echo $! > /tmp/lw-demo.pid
timeout 15 bash -c 'until curl -sf http://127.0.0.1:8765/healthz >/dev/null; do sleep 0.5; done'
```

`scripts/serve_demo.py` seeds `lidarr_url`/`lidarr_api_key`/`poll_interval`
settings plus a couple of sample `checks`/`blocklist_events` rows (see
`history.py`/`settings.py`) before calling `web.create_app(conn)` (no
`poll_interval` arg — the dashboard route reads it live from settings) and
`uvicorn.run(...)` — copy that pattern if you need different sample data.

Stop with `kill $(cat /tmp/lw-demo.pid)` (or `pkill -f serve_demo.py`)
before relaunching, or the next run hits a port conflict.

## Option B — real Lidarr instance available

```sh
LIDARR_URL=http://<host>:8686 LIDARR_API_KEY=<key> \
  LIDARR_WATCHDOG_DB_PATH=/tmp/lidarr-watchdog.db \
  .venv/bin/lidarr-watchdog &
```

This seeds those env vars into settings on first run, then runs the actual
poll loop against Lidarr. If the URL is unreachable, the error is caught,
logged, and recorded — the process doesn't crash and the dashboard shows
the error in a red status card. Verified this by pointing `LIDARR_URL` at
a nonexistent host. To change settings afterward, use the `/settings`
page (or edit the `settings` table directly) — re-exporting the env var
and restarting won't touch an already-seeded value.

## Driving the settings page

`/settings` is a plain server-rendered form (no JS) with two submit
buttons sharing one `<form>` — `Save settings` (`POST /settings`, redirects
to `/settings?saved=1`) and `Test connection` (`formaction="/settings/test"`,
re-renders the same page with a result banner, without persisting). With
Playwright: `page.fill("#lidarr_url", ...)`, `page.fill("#api_key", ...)`,
`page.check('input[name="deny_archives"]')`, then
`page.click('button:has-text("Save settings")')` or
`button:has-text("Test connection")`. The API key field is always rendered
blank (never echoes the stored secret); when a key is already saved, its
placeholder reads "unchanged — leave blank to keep".

## Screenshot (headless — this container has no display)

Playwright is not a project dependency; install it (and a browser engine)
into the venv the first time:

```sh
.venv/bin/pip install -q playwright
.venv/bin/playwright install chromium   # or: firefox
```

Browser binaries are cached at `~/.cache/ms-playwright` and persist across
sessions — the install step is a no-op after the first run. `--with-deps`
fails here (no passwordless sudo); the plain browser install works fine
without extra system packages.

```sh
.venv/bin/python .claude/skills/run/scripts/screenshot.py \
  http://127.0.0.1:8765/ /tmp/dashboard.png chromium
```

Pass `firefox` as the third arg to match a user who says they use Firefox
— for this app it renders identically either way (server-rendered
HTML/CSS, no client-side JS), but matching what the user actually runs
avoids the question coming up again.

Then view the PNG with the Read tool.

## Cleanup

```sh
pkill -f serve_demo.py 2>/dev/null || pkill -f lidarr-watchdog 2>/dev/null
rm -f /tmp/lidarr-watchdog-demo.db* /tmp/lidarr-watchdog.db* /tmp/dashboard.png
```

## Docker

See `README.md`'s Docker section and `Dockerfile` — `docker build -t
lidarr-watchdog .` then `docker run` with `LIDARR_URL`/`LIDARR_API_KEY`
and a volume at `/data`. Already verified end-to-end: build, `/healthz`,
dashboard error display on unreachable Lidarr, and SQLite history
surviving a container restart.
