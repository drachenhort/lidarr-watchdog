from lidarr_watchdog.watchdog import check_once, is_failed_import


class FakeLidarrClient:
    def __init__(self, queue):
        self._queue = queue
        self.removed = []

    def get_queue(self):
        return self._queue

    def remove_from_queue(self, queue_id, *, blocklist, skip_redownload):
        self.removed.append((queue_id, blocklist, skip_redownload))


def test_is_failed_import_true_for_import_failed_state():
    assert is_failed_import({"trackedDownloadState": "importFailed"})


def test_is_failed_import_false_for_other_states():
    assert not is_failed_import({"trackedDownloadState": "downloadFailed"})
    assert not is_failed_import({"trackedDownloadState": "importPending"})
    assert not is_failed_import({"trackedDownloadState": "importBlocked"})
    assert not is_failed_import({"trackedDownloadState": "imported"})
    assert not is_failed_import({})


def test_check_once_blocklists_and_requeues_failed_imports():
    queue = [
        {"id": 1, "title": "Good Album", "trackedDownloadState": "downloading"},
        {
            "id": 2,
            "title": "Stalled Download",
            "trackedDownloadStatus": "error",
            "trackedDownloadState": "downloadFailed",
        },
        {
            "id": 3,
            "title": "Bad Album",
            "trackedDownloadStatus": "warning",
            "trackedDownloadState": "importFailed",
            "statusMessages": [{"title": "Bad Album", "messages": ["Not a preferred word upgrade"]}],
        },
    ]
    client = FakeLidarrClient(queue)

    count = check_once(client)

    assert count == 1
    assert client.removed == [(3, True, False)]
