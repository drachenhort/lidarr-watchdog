# lidarr-watchdog

Polls a Lidarr instance's download queue, and for any item whose import
actually failed (queue `trackedDownloadState` of `importFailed`), blocklists
the release and lets Lidarr automatically search for a replacement. Other
queue warnings (stalled/failed downloads, pending manual import, etc.) are
left alone.

## Configuration

Set via environment variables:

| Variable                          | Required | Default | Description                              |
| ---------------------------------- | -------- | ------- | ---------------------------------------- |
| `LIDARR_URL`                       | yes      | —       | Base URL of your Lidarr instance         |
| `LIDARR_API_KEY`                   | yes      | —       | Lidarr API key (Settings → General)      |
| `LIDARR_WATCHDOG_POLL_INTERVAL`    | no       | `300`   | Seconds between queue checks             |

## Running

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
LIDARR_URL=http://localhost:8686 LIDARR_API_KEY=xxxx .venv/bin/lidarr-watchdog
```

The process runs continuously, checking the queue on the configured
interval, until stopped (SIGINT/SIGTERM).
