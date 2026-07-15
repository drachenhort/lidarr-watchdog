# lidarr-watchdog

Polls a Lidarr instance's download queue, and for any item whose import
actually failed (queue `trackedDownloadState` of `importFailed`), blocklists
the release and lets Lidarr automatically search for a replacement. Other
queue warnings (stalled/failed downloads, pending manual import, etc.) are
left alone.

A web dashboard shows the last check and recent blocklist events.

## Configuration

Set via environment variables:

| Variable                          | Required | Default               | Description                          |
| ---------------------------------- | -------- | ---------------------- | ------------------------------------- |
| `LIDARR_URL`                       | yes      | —                       | Base URL of your Lidarr instance     |
| `LIDARR_API_KEY`                   | yes      | —                       | Lidarr API key (Settings → General)  |
| `LIDARR_WATCHDOG_POLL_INTERVAL`    | no       | `300`                   | Seconds between queue checks         |
| `LIDARR_WATCHDOG_HOST`             | no       | `0.0.0.0`               | Web dashboard bind host              |
| `LIDARR_WATCHDOG_PORT`             | no       | `8000`                  | Web dashboard port                   |
| `LIDARR_WATCHDOG_DB_PATH`          | no       | `lidarr-watchdog.db`    | SQLite file for check/event history  |

## Running

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
LIDARR_URL=http://localhost:8686 LIDARR_API_KEY=xxxx .venv/bin/lidarr-watchdog
```

The process runs continuously: a background thread checks the queue on the
configured interval, while the dashboard is served at
`http://<host>:<port>/`. Stop with SIGINT/SIGTERM.

`LIDARR_WATCHDOG_DB_PATH` should point at a persistent location (e.g. a
mounted volume when running in a container) so history survives restarts.

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
