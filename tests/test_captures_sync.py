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
