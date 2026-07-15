"""Serve the lidarr-watchdog dashboard against a seeded, in-repo SQLite file —
no real Lidarr instance required. Useful for visually checking dashboard/
template changes.

Usage: python scripts/serve_demo.py [db_path] [port]
"""

import sys

import uvicorn

from lidarr_watchdog import history, settings
from lidarr_watchdog.web import create_app

db_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/lidarr-watchdog-demo.db"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765

conn = history.connect(db_path)

settings.set(conn, "lidarr_url", "http://lidarr.example:8686")
settings.set(conn, "lidarr_api_key", "demo-key")
settings.set(conn, "poll_interval", "300")

history.record_check(conn, failed_count=0)
history.record_check(conn, failed_count=2)
history.record_blocklist_event(
    conn,
    queue_id=101,
    title="Kind of Blue - Miles Davis",
    messages="Track count mismatch; unsupported archive",
)
history.record_blocklist_event(
    conn,
    queue_id=102,
    title="OK Computer - Radiohead",
    messages="Import failed: no files found eligible for import",
)
history.record_blocklist_event(
    conn,
    queue_id=103,
    title="Rumours - Fleetwood Mac",
    messages="Track count mismatch",
)

app = create_app(conn)
uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
