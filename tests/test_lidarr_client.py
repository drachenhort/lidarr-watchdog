import responses

from lidarr_watchdog.lidarr_client import LidarrClient


@responses.activate
def test_get_queue_returns_records_and_sends_api_key():
    responses.add(
        responses.GET,
        "http://lidarr.local/api/v1/queue",
        json={"page": 1, "pageSize": 200, "totalRecords": 1, "records": [{"id": 1}]},
        status=200,
    )

    client = LidarrClient("http://lidarr.local", "my-api-key")
    records = client.get_queue()

    assert records == [{"id": 1}]
    assert responses.calls[0].request.headers["X-Api-Key"] == "my-api-key"


@responses.activate
def test_get_queue_follows_pagination():
    responses.add(
        responses.GET,
        "http://lidarr.local/api/v1/queue",
        json={"page": 1, "pageSize": 1, "totalRecords": 2, "records": [{"id": 1}]},
        status=200,
    )
    responses.add(
        responses.GET,
        "http://lidarr.local/api/v1/queue",
        json={"page": 2, "pageSize": 1, "totalRecords": 2, "records": [{"id": 2}]},
        status=200,
    )

    client = LidarrClient("http://lidarr.local", "my-api-key")
    records = client.get_queue()

    assert records == [{"id": 1}, {"id": 2}]
    assert len(responses.calls) == 2


@responses.activate
def test_remove_from_queue_sends_blocklist_and_search_params():
    responses.add(
        responses.DELETE,
        "http://lidarr.local/api/v1/queue/42",
        status=200,
    )

    client = LidarrClient("http://lidarr.local", "my-api-key")
    client.remove_from_queue(42, blocklist=True, skip_redownload=False)

    request = responses.calls[0].request
    assert request.params["removeFromClient"] == "True"
    assert request.params["blocklist"] == "True"
    assert request.params["skipRedownload"] == "False"
