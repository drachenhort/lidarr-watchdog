from lidarr_watchdog import history


def test_record_and_get_last_check():
    conn = history.connect(":memory:")

    assert history.get_last_check(conn) is None

    history.record_check(conn, failed_count=2)
    history.record_check(conn, failed_count=0, error="boom")

    last = history.get_last_check(conn)
    assert last["failed_count"] == 0
    assert last["error"] == "boom"


def test_record_and_get_recent_events():
    conn = history.connect(":memory:")

    assert history.get_recent_events(conn) == []

    history.record_blocklist_event(conn, queue_id=1, title="First", messages="oops")
    history.record_blocklist_event(conn, queue_id=2, title="Second", messages="ouch")

    events = history.get_recent_events(conn)
    assert [event["title"] for event in events] == ["Second", "First"]


def test_get_recent_events_respects_limit():
    conn = history.connect(":memory:")

    for i in range(5):
        history.record_blocklist_event(conn, queue_id=i, title=f"Album {i}", messages="x")

    events = history.get_recent_events(conn, limit=2)
    assert len(events) == 2
    assert events[0]["title"] == "Album 4"


def test_repeat_count_starts_at_zero():
    conn = history.connect(":memory:")
    assert history.get_repeat_count(conn, album_id=1, reason="failed_import") == 0


def test_increment_repeat_count_increments_and_returns_new_value():
    conn = history.connect(":memory:")

    assert history.increment_repeat_count(conn, album_id=1, reason="failed_import") == 1
    assert history.increment_repeat_count(conn, album_id=1, reason="failed_import") == 2
    assert history.increment_repeat_count(conn, album_id=1, reason="failed_import") == 3

    assert history.get_repeat_count(conn, album_id=1, reason="failed_import") == 3


def test_repeat_count_tracked_independently_per_album_and_reason():
    conn = history.connect(":memory:")

    history.increment_repeat_count(conn, album_id=1, reason="failed_import")
    history.increment_repeat_count(conn, album_id=1, reason="failed_import")
    history.increment_repeat_count(conn, album_id=1, reason="denied")
    history.increment_repeat_count(conn, album_id=2, reason="failed_import")

    assert history.get_repeat_count(conn, album_id=1, reason="failed_import") == 2
    assert history.get_repeat_count(conn, album_id=1, reason="denied") == 1
    assert history.get_repeat_count(conn, album_id=2, reason="failed_import") == 1


def test_record_and_get_blocklist_only_events():
    conn = history.connect(":memory:")

    assert history.get_recent_blocklist_only_events(conn) == []

    history.record_blocklist_only_event(
        conn, queue_id=1, album_id=10, title="Repeat Offender", messages="Has missing tracks"
    )

    events = history.get_recent_blocklist_only_events(conn)
    assert len(events) == 1
    assert events[0]["title"] == "Repeat Offender"
    assert events[0]["album_id"] == 10


def test_record_and_get_ignore_events():
    conn = history.connect(":memory:")

    assert history.get_recent_ignore_events(conn) == []

    history.record_ignore_event(
        conn,
        queue_id=1,
        album_id=10,
        artist_id=5,
        title="Always An Archive",
        messages="Archive file detected",
    )

    events = history.get_recent_ignore_events(conn)
    assert len(events) == 1
    assert events[0]["title"] == "Always An Archive"
    assert events[0]["album_id"] == 10
    assert events[0]["artist_id"] == 5
