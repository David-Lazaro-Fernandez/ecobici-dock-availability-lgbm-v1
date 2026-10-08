from datetime import UTC, datetime, timedelta

import duckdb
import polars as pl
import pytest

from ecobici.features import model_matrix as mm
from ecobici.features import targets

# Tuesday 2025-03-04 15:00 UTC = 09:00 CDMX (train month). Snapshots every 15 min.
T0 = datetime(2025, 3, 4, 15, 0, tzinfo=UTC)
COORDS = {"A": (19.4300, -99.2000), "B": (19.4310, -99.2000), "C": (19.3850, -99.2000)}
# Filling up, then emptying.
A_DOCKS = [6, 4, 3, 1, 0, 0, 2, 5]


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
    # Docks 1 now; 3 at -15, 4 at -30, 6 at -45 (no -60).
    r = a_row(con, 45)
    assert (r["docks_lag15"], r["docks_lag30"], r["docks_lag60"]) == (3, 4, None)
    assert r["docks_delta15"] == -2 and r["full_lag15"] == 0


def test_neighbours_within_300m_only(con):
    # B (110 m) is full from snapshot 3; C (5 km) ignored.
    r = a_row(con, 45)
    assert r["nb_n"] == 1 and r["nb_full_frac"] == 1.0 and r["nb_docks_sum"] == 0


def test_flow_window_sums_slots_between_now_and_arrival(con):
    # 09:00 → 09:30: slots 36 and 37.
    r = a_row(con, 0)
    assert r["flow_net_window"] == pytest.approx(3.0)
    # Arrival slot 38.
    assert r["flow_arrivals_target"] == pytest.approx(4.0)


def test_weather_now_and_next_hour(con):
    # 09:30 CDMX = 15:30 UTC → hour 15:00 UTC.
    r = a_row(con, 30)
    assert (r["precip_now"], r["precip_next_hour"], r["temperature_now"]) == (0.0, 2.5, 15.0)


def test_calendar_and_station_profile(con):
    r = a_row(con, 0)
    assert r["weekday"] == 2 and r["weekend"] is False and r["holiday"] is False
    assert r["minute_of_day"] == 9 * 60
    # A full in 2 of 8 snapshots.
    assert r["st_full_rate"] == pytest.approx(2 / 8)


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
    # Slots 95 and 0, not 94 or 1.
    assert window == pytest.approx(2.0 + 3.0)


@pytest.mark.parametrize(
    ("window", "expected"),
    # Readings at 0, 17, 30 min (docks 9, 8, 7); at t = 30 the lag-15 target is 15.
    # trailing: latest reading <= 15 is at 0, older than 15 + 7.5 → missing.
    # centered: nearest within 15 ± 7.5 is the one at 17.
    [("trailing", None), ("centered", 8)],
)
def test_lag_window_trailing_vs_centered(tmp_path, window, expected):
    snaps = [
        {
            "station_id": "A",
            "committed_at_utc": T0 + timedelta(minutes=m),
            "is_installed": True,
            "is_returning": True,
            "num_docks_available": d,
            "num_bikes_available": 20 - d,
            "num_docks_disabled": 0,
            "capacity": 20,
            "latitude": 19.43,
            "longitude": -99.2,
        }
        for m, d in ((0, 9), (17, 8), (30, 7), (45, 6))
    ]
    path = tmp_path / "2025-03.parquet"
    pl.DataFrame(snaps).write_parquet(path)
    con = duckdb.connect()
    targets.load_snapshots(con, [path])
    empty_flow = pl.DataFrame(
        schema={
            "station_id": pl.String,
            "slot": pl.Int64,
            "weekend": pl.Boolean,
            "arrivals_mean": pl.Float64,
            "departures_mean": pl.Float64,
            "net_flow_mean": pl.Float64,
        }
    )
    weather = pl.DataFrame({"time_utc": [T0], "temperature_2m": [15.0], "precipitation": [0.0]})
    mm.prepare_shared(con, empty_flow, weather)
    targets.build_examples(con, 15)
    mm.build(con, 15, lag_window=window)
    r = con.execute(
        "SELECT docks_lag15, docks_delta15 FROM feat_15 WHERE t = ?", [T0 + timedelta(minutes=30)]
    ).fetchone()
    assert r[0] == expected
    assert r[1] == (None if expected is None else 7 - expected)


def test_lag_window_rejects_unknown(con):
    with pytest.raises(ValueError):
        mm.build(con, 30, lag_window="nearest")


def test_station_list_can_be_pinned_to_files(tmp_path):
    def snap(sid, minute):
        return {
            "station_id": sid,
            "committed_at_utc": T0 + timedelta(minutes=minute),
            "is_installed": True,
            "is_returning": True,
            "num_docks_available": 5,
            "num_bikes_available": 15,
            "num_docks_disabled": 0,
            "capacity": 20,
            "latitude": 19.43,
            "longitude": -99.2,
        }

    # "AA" only appears in the later file and sorts between "A" and "B".
    pl.DataFrame([snap("A", 0), snap("B", 0)]).write_parquet(tmp_path / "2025-03.parquet")
    pl.DataFrame([snap("A", 15), snap("AA", 15), snap("B", 15)]).write_parquet(
        tmp_path / "2026-01.parquet"
    )
    weather = pl.DataFrame({"time_utc": [T0], "temperature_2m": [15.0], "precipitation": [0.0]})
    flow = pl.DataFrame(
        schema={
            "station_id": pl.String,
            "slot": pl.Int64,
            "weekend": pl.Boolean,
            "arrivals_mean": pl.Float64,
            "departures_mean": pl.Float64,
            "net_flow_mean": pl.Float64,
        }
    )
    con = duckdb.connect()
    targets.load_snapshots(con, [tmp_path / "2025-03.parquet", tmp_path / "2026-01.parquet"])
    mm.prepare_shared(con, flow, weather)
    assert con.execute("SELECT sid, station FROM stations ORDER BY sid").fetchall() == [
        ("A", 0),
        ("AA", 1),
        ("B", 2),
    ]
    mm.prepare_shared(con, flow, weather, station_files=("2025-03",))
    assert con.execute("SELECT sid, station FROM stations ORDER BY sid").fetchall() == [
        ("A", 0),
        ("B", 1),
    ]


def test_short_lags_with_a_tight_tolerance_on_2min_readings(tmp_path):
    # Readings every 2 min; at t = 10 min the 2- and 4-min lags are the readings at 8 and 6.
    snaps = [
        {
            "station_id": "A",
            "committed_at_utc": T0 + timedelta(minutes=m),
            "is_installed": True,
            "is_returning": True,
            "num_docks_available": d,
            "num_bikes_available": 20 - d,
            "num_docks_disabled": 0,
            "capacity": 20,
            "latitude": 19.43,
            "longitude": -99.2,
        }
        for m, d in ((0, 9), (2, 8), (4, 7), (6, 6), (8, 5), (10, 4), (12, 3), (14, 2), (16, 1))
    ]
    path = tmp_path / "2026-10-07.parquet"
    pl.DataFrame(snaps).write_parquet(path)
    con = duckdb.connect()
    targets.load_snapshots(con, [path])
    flow = pl.DataFrame(
        schema={
            "station_id": pl.String,
            "slot": pl.Int64,
            "weekend": pl.Boolean,
            "arrivals_mean": pl.Float64,
            "departures_mean": pl.Float64,
            "net_flow_mean": pl.Float64,
        }
    )
    weather = pl.DataFrame({"time_utc": [T0], "temperature_2m": [15.0], "precipitation": [0.0]})
    mm.prepare_shared(con, flow, weather)
    targets.build_examples(con, 5, tolerance_min=1.0)
    out = mm.build(con, 5, lags=(2, 4), lag_window="centered", lag_tolerance_min=1.0, out="short")
    assert out == "short"
    r = con.execute(
        "SELECT docks_lag2, docks_lag4, docks_delta2, y FROM short WHERE t = ?",
        [T0 + timedelta(minutes=10)],
    ).fetchone()
    # Label: the reading within ±1 min of t + 5 → the one at 14 min (2 docks: not full).
    assert r == (5, 6, -1, False)
    assert set(mm.features((2, 4))) >= {"docks_lag2", "full_lag4"}
    assert "docks_lag15" not in mm.features((2, 4))
