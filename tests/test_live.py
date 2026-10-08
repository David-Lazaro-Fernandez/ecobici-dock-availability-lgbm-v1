import gzip
import json
from datetime import UTC, datetime, timedelta

import duckdb
import numpy as np
import polars as pl
from conftest import station, status_payload

from ecobici import live
from ecobici.collector.capture import object_key
from ecobici.collector.report import fetched_at
from ecobici.features import targets
from ecobici.models import lgbm

# 09:00 CDMX, a Wednesday.
T0 = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
INFO = {
    "data": {
        "stations": [
            {"station_id": "1", "capacity": 20, "lat": 19.41, "lon": -99.19},
            {"station_id": "2", "capacity": 10, "lat": 19.42, "lon": -99.18},
        ]
    }
}


def write_status(root, ts, stations):
    path = root / object_key("station_status", ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(status_payload(stations)).encode()))
    return path


def test_capture_rows_match_the_snapshot_schema(tmp_path):
    path = write_status(
        tmp_path,
        T0,
        [station("1", docks=0), station("2", docks=4, returning=0), station("99", docks=1)],
    )
    rows = live.capture_rows([path], INFO)
    # "99" has no station_information.
    assert rows["station_id"].to_list() == ["1", "2"]
    assert rows["committed_at_utc"].to_list() == [T0, T0]
    assert rows["is_returning"].to_list() == [True, False]
    assert rows["capacity"].to_list() == [20, 10]
    assert rows["latitude"].to_list() == [19.41, 19.42]

    # load_snapshots reads them like a MaxHalford file; the name sets file_month.
    file = tmp_path / "live_2026-10.parquet"
    rows.write_parquet(file)
    con = duckdb.connect()
    targets.load_snapshots(con, [file])
    snap = con.execute("SELECT sid, ok, is_full, file_month FROM snap ORDER BY sid").fetchall()
    assert snap == [("1", True, True, "2026-10"), ("2", False, False, "2026-10")]


def test_recent_captures_keep_the_lag_lookback(tmp_path):
    for minutes in (0, 60, 72, 74, 76):
        write_status(tmp_path, T0 + timedelta(minutes=minutes), [station("1")])
    got = [fetched_at(p) for p in live.recent_captures(tmp_path)]
    # Latest is +76; the lookback is 69.5 min, so +0 is out and +60 is the oldest kept.
    assert got == [T0 + timedelta(minutes=m) for m in (60, 72, 74, 76)]


def test_build_now_has_every_in_service_station_and_no_label(tmp_path):
    path = write_status(tmp_path, T0, [station("1", docks=0), station("2", returning=0)])
    file = tmp_path / "live_2026-10.parquet"
    live.capture_rows([path], INFO).write_parquet(file)
    con = duckdb.connect()
    targets.load_snapshots(con, [file])
    now = targets.build_now(con, 30, T0)
    r = con.execute(f"SELECT sid, slot, target_slot, weekend, full_now, y FROM {now}").fetchall()
    # 09:00 → arrival 09:30.
    assert r == [("1", 36, 38, False, True, None)]


class FakeBooster:
    def predict(self, X):
        return X[:, 0]


def test_frozen_applies_the_platt_only_to_the_subgroup():
    frozen = live.Frozen(
        FakeBooster(), np.array([0.0, 1.0]), np.array([0.0, 1.0]), lgbm.Platt(a=1.0, b=-1.0)
    )
    X = np.array([[0.4], [0.4], [1.5]])
    p, q = frozen.predict(X, np.array([True, False, False]))
    # Isotonic clips at its range.
    assert p.tolist() == [0.4, 0.4, 1.0]
    assert q[1:].tolist() == p[1:].tolist()
    assert np.isclose(q[0], lgbm.Platt(a=1.0, b=-1.0).predict(np.array([0.4]))[0])
    assert q[0] < p[0]


def test_forecast_weather_parses_open_meteo():
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "hourly": {
                    "time": ["2026-10-07T15:00", "2026-10-07T16:00"],
                    "temperature_2m": [18, 19.5],
                    "precipitation": [0, 1.2],
                }
            }

    class Session:
        def get(self, url, params, timeout):
            assert params["timezone"] == "GMT"
            return Resp()

    w = live.forecast_weather(session=Session())
    assert w.columns == ["temperature_2m", "precipitation", "time_utc"]
    assert w["time_utc"].to_list()[0] == T0
    assert w.schema["precipitation"] == pl.Float64
