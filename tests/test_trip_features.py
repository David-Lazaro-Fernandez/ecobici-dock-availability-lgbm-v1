from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from ecobici.features import trips as tf

CDMX = ZoneInfo("America/Mexico_City")
MAPPING = {"001": "A", "002": "B", "003": "C"}
TUE = datetime(2025, 3, 4, 8, 50, tzinfo=CDMX)  # Tuesday
SAT = datetime(2025, 3, 8, 8, 50, tzinfo=CDMX)


def trip(origin, dest, departed, minutes):
    return {
        "origin_code": origin,
        "destination_code": dest,
        "departed_at": departed,
        "arrived_at": departed + timedelta(minutes=minutes),
        "duration_min": float(minutes),
    }


@pytest.fixture
def root(tmp_path):
    rows = [
        trip("001", "002", TUE, 12),  # arrives B 09:02 → slot 36
        trip("001", "002", TUE + timedelta(days=1), 14),  # Wednesday, same slot
        trip("003", "002", TUE, 13),
        trip("002", "003", TUE + timedelta(minutes=20), 10),  # departs B 09:10
        trip("001", "002", SAT, 12),  # weekend
        trip("001", "001", TUE, 30),  # round trip: counted in flow, not in pairs
        trip("001", "002", TUE, 0.5),  # implausible
        trip("001", "999", TUE, 10),  # unmapped station
        trip("001", "002", TUE + timedelta(days=30), 12),  # outside the window
    ]
    pl.DataFrame(rows).write_parquet(tmp_path / "2025-03.parquet")
    return tmp_path


def window(root):
    start = datetime(2025, 3, 1, tzinfo=CDMX)
    return tf.load(start, start + timedelta(days=14), MAPPING, root)


def test_load_filters_window_plausibility_and_mapping(root):
    df = window(root).collect()
    assert df.height == 6
    assert set(df["destination_id"]) <= {"A", "B", "C"}


def test_net_flow_averages_over_days_of_each_type(root):
    flow = tf.net_flow(window(root))
    b = flow.filter(pl.col("station_id") == "B", pl.col("slot") == 36)
    weekday = b.filter(~pl.col("weekend")).row(0, named=True)
    # 3 weekday arrivals and 1 departure in slot 36 over 2 distinct weekdays.
    assert weekday["arrivals_mean"] == pytest.approx(3 / 2)
    assert weekday["departures_mean"] == pytest.approx(1 / 2)
    assert weekday["net_flow_mean"] == pytest.approx(1.0)
    weekend = b.filter(pl.col("weekend")).row(0, named=True)
    assert weekend["arrivals_mean"] == pytest.approx(1.0)


def test_pair_duration_skips_round_trips_and_sparse_pairs(root):
    pairs = tf.pair_duration(window(root), min_trips=2)
    assert pairs.select("origin_id", "destination_id", "hour").rows() == [("A", "B", 8)]
    row = pairs.row(0, named=True)
    assert row["n_trips"] == 3
    assert row["duration_median"] == pytest.approx(12)
