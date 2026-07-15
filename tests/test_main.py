from lidarr_watchdog import history
from lidarr_watchdog.main import check_and_record


class FakeLidarrClient:
    def __init__(self, queue):
        self._queue = queue
        self.removed = []

    def get_queue(self):
        return self._queue

    def remove_from_queue(self, queue_id, *, blocklist, skip_redownload):
        self.removed.append((queue_id, blocklist, skip_redownload))


def test_check_and_record_records_check_and_events():
    conn = history.connect(":memory:")
    client = FakeLidarrClient(
        [
            {
                "id": 3,
                "title": "Bad Album",
                "trackedDownloadState": "importFailed",
                "statusMessages": [{"title": "Bad Album", "messages": ["mismatched tracks"]}],
            }
        ]
    )

    count = check_and_record(client, conn)

    assert count == 1
    last_check = history.get_last_check(conn)
    assert last_check["failed_count"] == 1
    assert last_check["error"] is None

    events = history.get_recent_events(conn)
    assert len(events) == 1
    assert events[0]["title"] == "Bad Album"
    assert events[0]["messages"] == "mismatched tracks"


def test_check_and_record_captures_errors():
    conn = history.connect(":memory:")

    class BrokenClient:
        def get_queue(self):
            raise RuntimeError("connection refused")

    count = check_and_record(BrokenClient(), conn)

    assert count == 0
    last_check = history.get_last_check(conn)
    assert last_check["failed_count"] == 0
    assert "connection refused" in last_check["error"]
