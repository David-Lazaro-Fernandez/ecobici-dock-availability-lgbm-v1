import pytest

from ecobici.ingest import captures as cs


class FakeS3:
    """Two pages of listings; download_file writes ``size`` bytes."""

    def __init__(self, pages):
        self.pages = pages
        self.fetched = []

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return self

    def paginate(self, Bucket, Prefix):
        for page in self.pages:
            yield {"Contents": [o for o in page if o["Key"].startswith(Prefix)]}

    def download_file(self, bucket, key, filename):
        size = next(o["Size"] for p in self.pages for o in p if o["Key"] == key)
        self.fetched.append(key)
        with open(filename, "wb") as f:
            f.write(b"x" * size)


STATUS = "raw/station_status/2026/10/06/station_status_20261006T173722Z.json.gz"
INFO = "raw/station_information/2026/10/06/station_information_20261006T173722Z.json.gz"


def test_download_mirrors_keys_and_skips_same_size(tmp_path):
    s3 = FakeS3(
        [[{"Key": STATUS, "Size": 3}], [{"Key": INFO, "Size": 2}, {"Key": "raw/", "Size": 0}]]
    )

    assert cs.download("b", tmp_path, client=s3) == (2, 2)
    assert (tmp_path / STATUS.removeprefix("raw/")).stat().st_size == 3
    assert not list(tmp_path.rglob("*.tmp"))

    assert cs.download("b", tmp_path, client=s3) == (0, 2)
    assert len(s3.fetched) == 2


def test_download_one_feed(tmp_path):
    s3 = FakeS3([[{"Key": STATUS, "Size": 3}, {"Key": INFO, "Size": 2}]])
    assert cs.download("b", tmp_path, feed="station_status", client=s3) == (1, 1)
    assert s3.fetched == [STATUS]


def test_bucket_from_env_prefers_environment(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text("OTHER=1\nS3_BUCKET_NAME='from-file'\n")
    monkeypatch.delenv(cs.BUCKET_ENV, raising=False)
    assert cs.bucket_from_env(dotenv) == "from-file"
    monkeypatch.setenv(cs.BUCKET_ENV, "from-env")
    assert cs.bucket_from_env(dotenv) == "from-env"


def test_bucket_from_env_missing(tmp_path, monkeypatch):
    monkeypatch.delenv(cs.BUCKET_ENV, raising=False)
    with pytest.raises(SystemExit):
        cs.bucket_from_env(tmp_path / ".env")


def test_download_recent_lists_only_the_window_days(tmp_path):
    from datetime import UTC, datetime

    def key(day, ts):
        return f"raw/station_status/2026/10/{day}/station_status_202610{day}T{ts}Z.json.gz"

    old = key("06", "235800")  # before the window
    late = key("06", "235900")
    early = key("07", "000100")
    future = key("07", "001000")  # after `until`
    other_day = key("05", "120000")
    s3 = FakeS3([[{"Key": k, "Size": 1} for k in (other_day, old, late, early, future)]])
    listed = []
    paginate = s3.paginate
    s3.paginate = lambda Bucket, Prefix: (listed.append(Prefix), paginate(Bucket, Prefix))[1]

    got = cs.download_recent(
        "b",
        "station_status",
        since=datetime(2026, 10, 6, 23, 59, tzinfo=UTC),
        until=datetime(2026, 10, 7, 0, 5, tzinfo=UTC),
        dest=tmp_path,
        client=s3,
    )
    assert got == (2, 2)
    assert s3.fetched == [late, early]
    assert listed == ["raw/station_status/2026/10/06/", "raw/station_status/2026/10/07/"]
    # Already present with the same size: nothing new.
    assert cs.download_recent(
        "b",
        "station_status",
        since=datetime(2026, 10, 6, 23, 59, tzinfo=UTC),
        until=datetime(2026, 10, 7, 0, 5, tzinfo=UTC),
        dest=tmp_path,
        client=s3,
    ) == (0, 2)
