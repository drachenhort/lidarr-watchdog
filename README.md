# lidarr-watchdog

Polls a Lidarr instance's download queue, and for any item whose import
actually failed (queue `trackedDownloadState` of `importFailed`), blocklists
the release and lets Lidarr automatically search for a replacement. Other
queue warnings (stalled/failed downloads, pending manual import, etc.) are
left alone. Optionally, it can also proactively deny any queue item that's
an archive file (`.rar`/`.zip`/`.7z`) — see Settings below.

A web dashboard shows the last check and recent blocklist events, and a
Settings page lets you configure the Lidarr connection, check interval,
and archive-denial toggle at runtime — no restart required.

## Configuration

The Lidarr URL, API key, check interval, and archive-denial toggle are all
stored in the app's SQLite database and are editable live from the
**Settings** page (`/settings`) in the dashboard — changes take effect on
the next poll cycle, no restart needed.

Environment variables only *seed* those values the first time the app
starts (useful for Docker/first-run setup); once a value has been saved via
Settings, the env var is ignored on subsequent restarts:

| Variable                          | Required | Default               | Description                              |
| ---------------------------------- | -------- | ---------------------- | ----------------------------------------- |
| `LIDARR_URL`                       | no       | —                       | Seeds the Lidarr URL on first run         |
| `LIDARR_API_KEY`                   | no       | —                       | Seeds the Lidarr API key on first run     |
| `LIDARR_WATCHDOG_POLL_INTERVAL`    | no       | `300`                   | Seeds the check interval (seconds)        |
| `LIDARR_WATCHDOG_HOST`             | no       | `0.0.0.0`               | Web dashboard bind host                   |
| `LIDARR_WATCHDOG_PORT`             | no       | `8000`                  | Web dashboard port                        |
| `LIDARR_WATCHDOG_DB_PATH`          | no       | `lidarr-watchdog.db`    | SQLite file for settings/check history    |

If nothing is configured yet (no env vars, nothing saved via Settings),
the app still starts and serves the dashboard/Settings page — it just
records a "not configured" result each poll cycle until you set the URL
and API key in Settings.

## Running

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/lidarr-watchdog
```

Then open `http://localhost:8000/settings` to set the Lidarr URL and API
key (or pass `LIDARR_URL`/`LIDARR_API_KEY` as env vars to seed them on
first run). The process runs continuously: a background thread checks the
queue on the configured interval, while the dashboard is served at
`http://<host>:<port>/`. Stop with SIGINT/SIGTERM.

`LIDARR_WATCHDOG_DB_PATH` should point at a persistent location (e.g. a
mounted volume when running in a container) so settings and history
survive restarts.

## Docker

Pull the published image (built and pushed automatically on every `vX.Y.Z`
release tag):

```sh
docker pull ghcr.io/drachenhort/lidarr-watchdog:latest
# or pin a version: ghcr.io/drachenhort/lidarr-watchdog:0.3.0
```

Or build it yourself:

```sh
docker build -t lidarr-watchdog .
```

Run it:

```sh
docker run -d \
  --name lidarr-watchdog \
  -p 8000:8000 \
  -v lidarr-watchdog-data:/data \
  -e LIDARR_URL=http://lidarr:8686 \
  -e LIDARR_API_KEY=xxxx \
  ghcr.io/drachenhort/lidarr-watchdog:latest
```

The image stores its SQLite history at `/data/lidarr-watchdog.db` by
default — mount a volume there to keep history across container restarts.
The dashboard is served on port `8000`.
