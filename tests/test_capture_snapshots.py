import gzip
import json
from datetime import UTC, datetime, timedelta

import polars as pl
from conftest import station, status_payload

from ecobici import config
from ecobici.collector.capture import object_key
from ecobici.ingest import capture_snapshots as cs

T0 = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
INFO = {
    "last_updated": 1,
    "data": {
        "stations": [
            {
                "station_id": s,
                "short_name": s,
                "name": s,
                "lat": 19.4,
                "lon": -99.17,
                "capacity": 20,
            }
            for s in ("1", "2")
        ]
    },
}


def write(root, feed, ts, payload):
    path = root / object_key(feed, ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(payload).encode()))


def test_build_writes_one_file_per_day_drops_stale_and_skips_unchanged_days(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "out"
    write(raw, "station_information", T0, INFO)
    for day, minutes in ((0, (0, 2)), (1, (0,))):
        for m in minutes:
            ts = T0 + timedelta(days=day, minutes=m)
            lu = int(ts.timestamp())
            stale = lu - config.STALE_AFTER_SECONDS - 60
            write(
                raw,
                "station_status",
                ts,
                status_payload(
                    [station("1", last_reported=lu), station("2", last_reported=stale)], lu
                ),
            )
    logs = []
    files = cs.build(raw, out, log=logs.append)
    assert [f.name for f in files] == ["2026-10-07.parquet", "2026-10-08.parquet"]
    day1 = pl.read_parquet(files[0])
    assert day1["station_id"].to_list() == ["1", "1"]  # station 2 is stale
    assert day1.columns[:2] == ["station_id", "committed_at_utc"]
    assert len(logs) == 2
    # Nothing changed: nothing rebuilt.
    logs.clear()
    cs.build(raw, out, log=logs.append)
    assert logs == []
