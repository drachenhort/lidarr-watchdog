from __future__ import annotations

from typing import Any

import requests


class LidarrClient:
    def __init__(
        self, base_url: str, api_key: str, session: requests.Session | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._session.headers.update({"X-Api-Key": api_key})

    def get_queue(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page = 1
        while True:
            response = self._session.get(
                f"{self._base_url}/api/v1/queue",
                params={"page": page, "pageSize": 200, "includeUnknownArtistItems": True},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            page_records = payload.get("records", [])
            records.extend(page_records)
            # Guard against a malformed/zero pageSize looping forever: stop
            # once a page comes back empty, regardless of totalRecords math.
            if not page_records or page * payload.get("pageSize", 200) >= payload.get(
                "totalRecords", 0
            ):
                break
            page += 1
        return records

    def remove_from_queue(
        self, queue_id: int, *, blocklist: bool = True, skip_redownload: bool = False
    ) -> None:
        response = self._session.delete(
            f"{self._base_url}/api/v1/queue/{queue_id}",
            params={
                "removeFromClient": True,
                "blocklist": blocklist,
                "skipRedownload": skip_redownload,
            },
            timeout=30,
        )
        response.raise_for_status()

    def get_blocklist(self, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        response = self._session.get(
            f"{self._base_url}/api/v1/blocklist",
            params={
                "page": page,
                "pageSize": page_size,
                "sortKey": "date",
                "sortDirection": "descending",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def remove_blocklist_entry(self, blocklist_id: int) -> None:
        response = self._session.delete(
            f"{self._base_url}/api/v1/blocklist/{blocklist_id}", timeout=30
        )
        response.raise_for_status()

    def unmonitor_album(self, album_id: int) -> None:
        response = self._session.get(f"{self._base_url}/api/v1/album/{album_id}", timeout=30)
        response.raise_for_status()
        album = response.json()
        album["monitored"] = False
        response = self._session.put(
            f"{self._base_url}/api/v1/album/{album_id}", json=album, timeout=30
        )
        response.raise_for_status()
