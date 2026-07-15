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

## Option A — no real Lidarr instance (dashboard-only, for UI/template work)

`main.py` requires `LIDARR_URL`/`LIDARR_API_KEY` and immediately starts
polling a real Lidarr, which isn't useful for just checking how the
dashboard renders. Instead, seed the SQLite history directly and serve the
FastAPI app on its own, bypassing the poll loop entirely:

```sh
.venv/bin/python .claude/skills/run/scripts/serve_demo.py /tmp/lidarr-watchdog-demo.db 8765 &
echo $! > /tmp/lw-demo.pid
timeout 15 bash -c 'until curl -sf http://127.0.0.1:8765/healthz >/dev/null; do sleep 0.5; done'
```

`scripts/serve_demo.py` writes a couple of sample `checks`/
`blocklist_events` rows (see `history.py`) before calling
`web.create_app(conn, poll_interval)` and `uvicorn.run(...)` — copy that
pattern if you need different sample data.

Stop with `kill $(cat /tmp/lw-demo.pid)` (or `pkill -f serve_demo.py`)
before relaunching, or the next run hits a port conflict.

## Option B — real Lidarr instance available

```sh
LIDARR_URL=http://<host>:8686 LIDARR_API_KEY=<key> \
  LIDARR_WATCHDOG_DB_PATH=/tmp/lidarr-watchdog.db \
  .venv/bin/lidarr-watchdog &
```

This runs the actual poll loop against Lidarr. If the URL is unreachable,
the error is caught, logged, and recorded — the process doesn't crash and
the dashboard shows the error in a red status card. Verified this by
pointing `LIDARR_URL` at a nonexistent host.

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
