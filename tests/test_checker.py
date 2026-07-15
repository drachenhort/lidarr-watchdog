from lidarr_watchdog import history, settings
from lidarr_watchdog.checker import check_and_record, resolve_client, run_check_cycle
from lidarr_watchdog.lidarr_client import LidarrClient


class FakeLidarrClient:
    def __init__(self, queue):
        self._queue = queue
        self.removed = []
        self.unmonitored_albums = []

    def get_queue(self):
        return self._queue

    def remove_from_queue(self, queue_id, *, blocklist, skip_redownload):
        self.removed.append((queue_id, blocklist, skip_redownload))

    def unmonitor_album(self, album_id):
        self.unmonitored_albums.append(album_id)


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


def test_check_and_record_denies_archives_when_setting_enabled():
    conn = history.connect(":memory:")
    settings.set_deny_archives(conn, True)
    client = FakeLidarrClient(
        [{"id": 9, "title": "Archive.Album.rar", "trackedDownloadState": "downloading"}]
    )

    count = check_and_record(client, conn)

    assert count == 1
    assert client.removed == [(9, True, False)]
    events = history.get_recent_events(conn)
    assert events[0]["messages"] == "Archive file detected (deny archives is enabled)"


def test_check_and_record_denies_executables_when_setting_enabled():
    conn = history.connect(":memory:")
    settings.set_deny_executables(conn, True)
    client = FakeLidarrClient(
        [{"id": 10, "title": "Malware.Album.exe", "trackedDownloadState": "downloading"}]
    )

    count = check_and_record(client, conn)

    assert count == 1
    assert client.removed == [(10, True, False)]
    events = history.get_recent_events(conn)
    assert events[0]["messages"] == "Executable file detected (deny executables is enabled)"


def test_resolve_client_none_when_unconfigured():
    conn = history.connect(":memory:")
    assert resolve_client(conn) is None


def test_resolve_client_builds_client_when_configured():
    conn = history.connect(":memory:")
    settings.set(conn, "lidarr_url", "http://lidarr:8686")
    settings.set(conn, "lidarr_api_key", "secret")

    client = resolve_client(conn)

    assert isinstance(client, LidarrClient)


def test_run_check_cycle_records_error_when_unconfigured():
    conn = history.connect(":memory:")

    count = run_check_cycle(conn)

    assert count == 0
    last_check = history.get_last_check(conn)
    assert "isn't configured" in last_check["error"]


def _failed_import_record(queue_id, album_id, title="Repeat Offender"):
    return {
        "id": queue_id,
        "title": title,
        "albumId": album_id,
        "trackedDownloadState": "importFailed",
        "statusMessages": [{"title": title, "messages": ["Has missing tracks"]}],
    }


def test_repeat_failed_import_below_threshold_stays_normal_blocklist():
    conn = history.connect(":memory:")
    settings.set_repeat_threshold(conn, 3)

    for queue_id in (1, 2):
        client = FakeLidarrClient([_failed_import_record(queue_id, album_id=100)])
        check_and_record(client, conn)
        assert client.removed == [(queue_id, True, False)]  # normal: still auto-researching

    assert len(history.get_recent_events(conn)) == 2
    assert history.get_recent_blocklist_only_events(conn) == []


def test_repeat_failed_import_at_threshold_escalates_to_blocklist_only():
    conn = history.connect(":memory:")
    settings.set_repeat_threshold(conn, 3)

    # Two below-threshold occurrences first
    for queue_id in (1, 2):
        client = FakeLidarrClient([_failed_import_record(queue_id, album_id=100)])
        check_and_record(client, conn)

    # Third occurrence for the same album crosses the threshold
    client = FakeLidarrClient([_failed_import_record(3, album_id=100)])
    count = check_and_record(client, conn)

    assert count == 1
    assert client.removed == [(3, True, True)]  # skip_redownload now True
    assert client.unmonitored_albums == []  # failed-import escalation never unmonitors

    blocklist_only = history.get_recent_blocklist_only_events(conn)
    assert len(blocklist_only) == 1
    assert blocklist_only[0]["queue_id"] == 3
    assert blocklist_only[0]["album_id"] == 100
    # regular blocklist_events log only has the first two (below-threshold) occurrences
    assert len(history.get_recent_events(conn)) == 2


def _denied_archive_record(queue_id, album_id, artist_id=55, title="Always An Archive.rar"):
    return {
        "id": queue_id,
        "title": title,
        "albumId": album_id,
        "artistId": artist_id,
        "trackedDownloadState": "downloading",
    }


def test_repeat_denied_at_threshold_unmonitors_album_and_records_ignore_event():
    conn = history.connect(":memory:")
    settings.set_repeat_threshold(conn, 2)
    settings.set_deny_archives(conn, True)

    client1 = FakeLidarrClient([_denied_archive_record(1, album_id=200)])
    check_and_record(client1, conn)
    assert client1.unmonitored_albums == []

    client2 = FakeLidarrClient([_denied_archive_record(2, album_id=200)])
    count = check_and_record(client2, conn)

    assert count == 1
    assert client2.removed == [(2, True, True)]
    assert client2.unmonitored_albums == [200]

    ignore_events = history.get_recent_ignore_events(conn)
    assert len(ignore_events) == 1
    assert ignore_events[0]["album_id"] == 200
    assert ignore_events[0]["artist_id"] == 55
    assert ignore_events[0]["queue_id"] == 2
    assert history.get_recent_blocklist_only_events(conn) == []


def test_failed_import_and_denied_counters_are_independent_per_album():
    conn = history.connect(":memory:")
    settings.set_repeat_threshold(conn, 2)
    settings.set_deny_archives(conn, True)

    # One failed-import occurrence and one denied occurrence for the SAME
    # album must not share a counter.
    client1 = FakeLidarrClient([_failed_import_record(1, album_id=300)])
    check_and_record(client1, conn)
    client2 = FakeLidarrClient([_denied_archive_record(2, album_id=300)])
    check_and_record(client2, conn)

    assert history.get_repeat_count(conn, album_id=300, reason="failed_import") == 1
    assert history.get_repeat_count(conn, album_id=300, reason="denied") == 1
    # neither reached threshold 2 on its own, so neither escalated
    assert history.get_recent_blocklist_only_events(conn) == []
    assert history.get_recent_ignore_events(conn) == []


def test_records_without_album_id_never_escalate():
    conn = history.connect(":memory:")
    settings.set_repeat_threshold(conn, 1)  # threshold of 1: would escalate immediately if tracked

    for queue_id in (1, 2, 3):
        record = _failed_import_record(queue_id, album_id=None)
        del record["albumId"]
        client = FakeLidarrClient([record])
        check_and_record(client, conn)
        assert client.removed == [(queue_id, True, False)]

    assert len(history.get_recent_events(conn)) == 3
    assert history.get_recent_blocklist_only_events(conn) == []
    assert history.get_recent_ignore_events(conn) == []


def test_unmonitor_album_failure_does_not_prevent_ignore_event_from_being_recorded():
    conn = history.connect(":memory:")
    settings.set_repeat_threshold(conn, 1)
    settings.set_deny_archives(conn, True)

    class FailingUnmonitorClient(FakeLidarrClient):
        def unmonitor_album(self, album_id):
            raise RuntimeError("Lidarr API error")

    client = FailingUnmonitorClient([_denied_archive_record(1, album_id=400)])
    count = check_and_record(client, conn)

    assert count == 1
    ignore_events = history.get_recent_ignore_events(conn)
    assert len(ignore_events) == 1
    assert ignore_events[0]["album_id"] == 400
