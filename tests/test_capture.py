import gzip
from datetime import UTC, datetime

import pytest
import requests
from conftest import FakeResponse, FakeSession

from ecobici.collector import capture as cap
from ecobici.collector.sinks import LocalSink, S3Sink, sink_from_uri


def test_object_key_is_utc_and_partitioned_by_day():
    ts = datetime(2026, 10, 6, 23, 58, 0, tzinfo=UTC)
    assert cap.object_key("station_status", ts) == (
        "station_status/2026/10/06/station_status_20261006T235800Z.json.gz"
    )


def test_validate_counts_stations(status_body):
    assert cap.validate("station_status", status_body) == (1_000_000, 2)


def test_validate_accepts_feed_without_stations():
    assert cap.validate("system_information", b'{"last_updated": 5, "data": {}}') == (5, None)


@pytest.mark.parametrize(
    "body",
    [b"<html>error</html>", b'{"data": {}}', b'{"last_updated": 1, "data": {"stations": []}}'],
)
def test_validate_rejects_bad_payloads(body):
    with pytest.raises(cap.InvalidPayload):
        cap.validate("station_status", body)


def test_capture_stores_raw_bytes_gzipped(tmp_path, status_body):
    result = cap.capture(
        "station_status", LocalSink(tmp_path), FakeSession(FakeResponse(status_body))
    )
    stored = list(tmp_path.rglob("*.json.gz"))
    assert len(stored) == 1
    assert gzip.decompress(stored[0].read_bytes()) == status_body
    assert result.n_stations == 2
    assert not list(tmp_path.rglob("*.tmp"))


def test_capture_does_not_store_invalid_payload(tmp_path):
    with pytest.raises(cap.InvalidPayload):
        cap.capture("station_status", LocalSink(tmp_path), FakeSession(FakeResponse(b"oops")))
    assert not list(tmp_path.rglob("*"))


def test_fetch_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(cap.time, "sleep", lambda s: None)
    session = FakeSession(requests.ConnectionError("down"), FakeResponse(b"ok"))
    assert cap.fetch("http://x", session) == b"ok"
    assert session.calls == 2


def test_fetch_gives_up_after_attempts(monkeypatch):
    monkeypatch.setattr(cap.time, "sleep", lambda s: None)
    session = FakeSession(*[FakeResponse(b"", status=503)] * 3)
    with pytest.raises(requests.HTTPError):
        cap.fetch("http://x", session, attempts=3)
    assert session.calls == 3


def test_sink_from_uri():
    assert isinstance(sink_from_uri("/tmp/raw"), LocalSink)
    assert isinstance(sink_from_uri("file:///tmp/raw"), LocalSink)
    with pytest.raises(ValueError):
        sink_from_uri("gs://bucket")


def test_s3_sink_prefixes_key():
    class FakeS3:
        def put_object(self, **kw):
            self.kw = kw

    client = FakeS3()
    loc = S3Sink("bkt", "/raw/", client=client).put("station_status/a.json.gz", b"x")
    assert loc == "s3://bkt/raw/station_status/a.json.gz"
    assert client.kw["Key"] == "raw/station_status/a.json.gz"
    assert client.kw["ContentEncoding"] == "gzip"
