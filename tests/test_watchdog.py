from lidarr_watchdog.watchdog import check_once, is_archive, is_failed_import


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


def test_check_once_invokes_on_blocklisted_callback():
    queue = [
        {"id": 1, "title": "Bad Album", "trackedDownloadState": "importFailed"},
    ]
    client = FakeLidarrClient(queue)
    seen = []

    check_once(client, on_blocklisted=seen.append)

    assert [record["id"] for record in seen] == [1]


def test_is_archive_matches_common_extensions():
    assert is_archive({"title": "Some.Album-2020-GROUP.rar"})
    assert is_archive({"title": "Some.Album.part002.rar"})
    assert is_archive({"title": "Some.Album-GROUP.zip"})
    assert is_archive({"title": "Some.Album-GROUP.7z"})
    assert is_archive({"title": "Some.Album-GROUP.r01"})


def test_is_archive_false_for_non_archive():
    assert not is_archive({"title": "Some.Album-2020-FLAC-GROUP"})
    assert not is_archive({})


def test_check_once_ignores_archives_when_deny_archives_disabled():
    queue = [
        {"id": 1, "title": "Archive.Album.rar", "trackedDownloadState": "downloading"},
    ]
    client = FakeLidarrClient(queue)

    count = check_once(client, deny_archives=False)

    assert count == 0
    assert client.removed == []


def test_check_once_denies_archives_when_enabled():
    queue = [
        {"id": 1, "title": "Good Album", "trackedDownloadState": "downloading"},
        {"id": 2, "title": "Archive.Album.rar", "trackedDownloadState": "downloading"},
    ]
    client = FakeLidarrClient(queue)

    count = check_once(client, deny_archives=True)

    assert count == 1
    assert client.removed == [(2, True, False)]


def test_check_once_does_not_double_count_failed_archive():
    queue = [
        {
            "id": 1,
            "title": "Archive.Album.rar",
            "trackedDownloadState": "importFailed",
            "statusMessages": [{"title": "x", "messages": ["Has unmatched tracks"]}],
        },
    ]
    client = FakeLidarrClient(queue)

    count = check_once(client, deny_archives=True)

    assert count == 1
    assert client.removed == [(1, True, False)]
