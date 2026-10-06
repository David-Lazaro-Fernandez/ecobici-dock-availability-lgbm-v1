import json

import pytest
import requests


def station(sid, docks=5, installed=1, returning=1, last_reported=1_000_000):
    return {
        "station_id": sid,
        "num_docks_available": docks,
        "num_bikes_available": 3,
        "is_installed": installed,
        "is_renting": 1,
        "is_returning": returning,
        "last_reported": last_reported,
    }


def status_payload(stations, last_updated=1_000_000):
    return {"last_updated": last_updated, "ttl": 10, "data": {"stations": stations}}


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.content = body
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Returns queued responses in order; an Exception in the queue is raised."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def status_body():
    return json.dumps(status_payload([station("1"), station("2", docks=0)])).encode()
