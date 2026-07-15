from lidarr_watchdog.watchdog import (
    check_once,
    is_archive,
    is_executable,
    is_failed_import,
    status_messages,
)


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


def test_check_once_invokes_on_blocklisted_callback_with_reason():
    queue = [
        {"id": 1, "title": "Bad Album", "trackedDownloadState": "importFailed"},
    ]
    client = FakeLidarrClient(queue)
    seen = []

    check_once(client, on_blocklisted=lambda record, reason: seen.append((record["id"], reason)))

    assert seen == [(1, "failed_import")]


def test_check_once_passes_archive_and_executable_reasons():
    queue = [
        {"id": 1, "title": "Archive.Album.rar", "trackedDownloadState": "downloading"},
        {"id": 2, "title": "Malware.Album.exe", "trackedDownloadState": "downloading"},
    ]
    client = FakeLidarrClient(queue)
    seen = []

    check_once(
        client,
        on_blocklisted=lambda record, reason: seen.append((record["id"], reason)),
        deny_archives=True,
        deny_executables=True,
    )

    assert seen == [(1, "archive"), (2, "executable")]


def test_check_once_uses_resolve_skip_redownload_per_record():
    queue = [
        {"id": 1, "title": "First Offender", "trackedDownloadState": "importFailed"},
        {"id": 2, "title": "Repeat Offender", "trackedDownloadState": "importFailed"},
    ]
    client = FakeLidarrClient(queue)

    def resolve(record, reason):
        return record["id"] == 2

    check_once(client, resolve_skip_redownload=resolve)

    assert client.removed == [(1, True, False), (2, True, True)]


def test_check_once_defaults_skip_redownload_false_without_resolver():
    queue = [{"id": 1, "title": "Bad Album", "trackedDownloadState": "importFailed"}]
    client = FakeLidarrClient(queue)

    check_once(client)

    assert client.removed == [(1, True, False)]


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


def test_is_executable_matches_common_extensions():
    assert is_executable({"title": "Some.Album-2020-GROUP.exe"})
    assert is_executable({"title": "Setup.msi"})
    assert is_executable({"title": "install.bat"})
    assert is_executable({"title": "run.cmd"})
    assert is_executable({"title": "old.com"})
    assert is_executable({"title": "screensaver.scr"})
    assert is_executable({"title": "script.vbs"})
    assert is_executable({"title": "script.ps1"})


def test_is_executable_false_for_non_executable():
    assert not is_executable({"title": "Some.Album-2020-FLAC-GROUP"})
    assert not is_executable({})


def test_check_once_ignores_executables_when_deny_executables_disabled():
    queue = [
        {"id": 1, "title": "Malware.Album.exe", "trackedDownloadState": "downloading"},
    ]
    client = FakeLidarrClient(queue)

    count = check_once(client, deny_executables=False)

    assert count == 0
    assert client.removed == []


def test_check_once_denies_executables_when_enabled():
    queue = [
        {"id": 1, "title": "Good Album", "trackedDownloadState": "downloading"},
        {"id": 2, "title": "Malware.Album.exe", "trackedDownloadState": "downloading"},
    ]
    client = FakeLidarrClient(queue)

    count = check_once(client, deny_executables=True)

    assert count == 1
    assert client.removed == [(2, True, False)]


def test_check_once_denies_both_archives_and_executables():
    queue = [
        {"id": 1, "title": "Archive.Album.rar", "trackedDownloadState": "downloading"},
        {"id": 2, "title": "Malware.Album.exe", "trackedDownloadState": "downloading"},
        {"id": 3, "title": "Good Album", "trackedDownloadState": "downloading"},
    ]
    client = FakeLidarrClient(queue)

    count = check_once(client, deny_archives=True, deny_executables=True)

    assert count == 2
    assert {removed[0] for removed in client.removed} == {1, 2}


def test_status_messages_deduplicates_repeated_per_track_messages():
    # Lidarr emits one statusMessages entry per track, so an album-level
    # issue is repeated once per track (e.g. 12 times for a 12-track album)
    record = {
        "statusMessages": [
            {
                "title": f"Track {i}",
                "messages": [
                    "Album match is not close enough: 27.6 % vs 80 %",
                    "Has unmatched tracks",
                ],
            }
            for i in range(12)
        ]
    }

    assert status_messages(record) == [
        "Album match is not close enough: 27.6 % vs 80 %",
        "Has unmatched tracks",
    ]


def test_status_messages_preserves_order_of_first_occurrence():
    record = {
        "statusMessages": [
            {"title": "Track 1", "messages": ["A", "B"]},
            {"title": "Track 2", "messages": ["B", "C"]},
            {"title": "Track 3", "messages": ["A"]},
        ]
    }

    assert status_messages(record) == ["A", "B", "C"]


def test_status_messages_empty_for_no_status_messages():
    assert status_messages({}) == []
    assert status_messages({"statusMessages": []}) == []


def test_check_once_deduplicates_messages_in_denial_log():
    queue = [
        {
            "id": 1,
            "title": "Repeated Reasons Album",
            "trackedDownloadState": "importFailed",
            "statusMessages": [
                {"title": "Track 1", "messages": ["Album match is not close enough"]},
                {"title": "Track 2", "messages": ["Album match is not close enough"]},
                {"title": "Track 3", "messages": ["Album match is not close enough"]},
            ],
        }
    ]
    client = FakeLidarrClient(queue)
    seen = []

    check_once(client, on_blocklisted=lambda record, reason: seen.append(status_messages(record)))

    assert seen == [["Album match is not close enough"]]
