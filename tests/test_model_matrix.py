from datetime import UTC, datetime, timedelta

import duckdb
import polars as pl
import pytest

from ecobici.features import model_matrix as mm
from ecobici.features import targets

# Tuesday 2025-03-04 15:00 UTC = 09:00 CDMX (train month). Snapshots every 15 min.
T0 = datetime(2025, 3, 4, 15, 0, tzinfo=UTC)
COORDS = {"A": (19.4300, -99.2000), "B": (19.4310, -99.2000), "C": (19.3850, -99.2000)}
A_DOCKS = [6, 4, 3, 1, 0, 0, 2, 5]  # filling up, then emptying


def rows():
    out = []
    for i, a_docks in enumerate(A_DOCKS):
        t = T0 + timedelta(minutes=15 * i)
        for sid, (lat, lon) in COORDS.items():
            docks = a_docks if sid == "A" else (0 if sid == "B" and i >= 3 else 7)
            out.append(
                {
                    "station_id": sid,
                    "committed_at_utc": t,
                    "is_installed": True,
                    "is_returning": True,
                    "num_docks_available": docks,
                    "num_bikes_available": 20 - docks,
                    "num_docks_disabled": 0,
                    "capacity": 20,
                    "latitude": lat,
                    "longitude": lon,
                }
            )
    return out


@pytest.fixture
def con(tmp_path):
    path = tmp_path / "2025-03.parquet"
    pl.DataFrame(rows()).write_parquet(path)
    con = duckdb.connect()
    targets.load_snapshots(con, [path])
    flow = pl.DataFrame(
        {
            "station_id": ["A", "A", "A"],
            "slot": [36, 37, 38],
            "weekend": [False] * 3,
            "arrivals_mean": [2.0, 3.0, 4.0],
            "departures_mean": [1.0, 1.0, 1.0],
            "net_flow_mean": [1.0, 2.0, 3.0],
        }
    )
    weather = pl.DataFrame(
        {
            "time_utc": [T0, T0 + timedelta(hours=1), T0 + timedelta(hours=2)],
            "temperature_2m": [15.0, 16.0, 17.0],
            "precipitation": [0.0, 2.5, 0.0],
        }
    )
    mm.prepare_shared(con, flow, weather)
    targets.build_examples(con, 30)
    mm.build(con, 30)
    return con


def a_row(con, minute):
    t = T0 + timedelta(minutes=minute)
    df = con.execute("SELECT * EXCLUDE (t) FROM feat_30 WHERE sid = 'A' AND t = ?", [t]).pl()
    assert df.height == 1
    return df.row(0, named=True)


def test_all_declared_features_exist(con):
    cols = {d[0] for d in con.execute("SELECT * FROM feat_30 LIMIT 0").description}
    assert set(mm.FEATURES) <= cols


def test_lags_use_past_snapshots_only(con):
    r = a_row(con, 45)  # docks 1 now; 3 at -15, 4 at -30, 6 at -45 (no -60)
    assert (r["docks_lag15"], r["docks_lag30"], r["docks_lag60"]) == (3, 4, None)
    assert r["docks_delta15"] == -2 and r["full_lag15"] == 0


def test_neighbours_within_300m_only(con):
    r = a_row(con, 45)  # B (110 m) is full from snapshot 3; C (5 km) ignored
    assert r["nb_n"] == 1 and r["nb_full_frac"] == 1.0 and r["nb_docks_sum"] == 0


def test_flow_window_sums_slots_between_now_and_arrival(con):
    r = a_row(con, 0)  # 09:00 → 09:30: slots 36 and 37
    assert r["flow_net_window"] == pytest.approx(3.0)
    assert r["flow_arrivals_target"] == pytest.approx(4.0)  # arrival slot 38


def test_weather_now_and_next_hour(con):
    r = a_row(con, 30)  # 09:30 CDMX = 15:30 UTC → hour 15:00 UTC
    assert (r["precip_now"], r["precip_next_hour"], r["temperature_now"]) == (0.0, 2.5, 15.0)


def test_calendar_and_station_profile(con):
    r = a_row(con, 0)
    assert r["weekday"] == 2 and r["weekend"] is False and r["holiday"] is False
    assert r["minute_of_day"] == 9 * 60
    assert r["st_full_rate"] == pytest.approx(2 / 8)  # A full in 2 of 8 snapshots


def test_flow_window_dates():
    start, end = mm.flow_window()
    assert (start.isoformat(), end.isoformat()) == ("2024-09-01", "2025-07-01")


def test_flow_window_wraps_past_midnight(tmp_path):
    # Tuesday 23:45 CDMX = Wednesday 05:45 UTC; h=30 → arrival 00:15 (slot 1).
    start = datetime(2025, 3, 5, 5, 45, tzinfo=UTC)
    snaps = [
        {
            "station_id": "A",
            "committed_at_utc": start + timedelta(minutes=15 * i),
            "is_installed": True,
            "is_returning": True,
            "num_docks_available": 5,
            "num_bikes_available": 15,
            "num_docks_disabled": 0,
            "capacity": 20,
            "latitude": 19.43,
            "longitude": -99.2,
        }
        for i in range(3)
    ]
    path = tmp_path / "2025-03.parquet"
    pl.DataFrame(snaps).write_parquet(path)
    con = duckdb.connect()
    targets.load_snapshots(con, [path])
    flow = pl.DataFrame(
        {
            "station_id": ["A"] * 4,
            "slot": [94, 95, 0, 1],
            "weekend": [False] * 4,
            "arrivals_mean": [1.0] * 4,
            "departures_mean": [0.0] * 4,
            "net_flow_mean": [10.0, 2.0, 3.0, 100.0],
        }
    )
    weather = pl.DataFrame({"time_utc": [start], "temperature_2m": [15.0], "precipitation": [0.0]})
    mm.prepare_shared(con, flow, weather)
    targets.build_examples(con, 30)
    mm.build(con, 30)
    (window,) = con.execute("SELECT flow_net_window FROM feat_30 WHERE t = ?", [start]).fetchone()
    assert window == pytest.approx(2.0 + 3.0)  # slots 95 and 0, not 94 or 1
