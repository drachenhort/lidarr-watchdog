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
