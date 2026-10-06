from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from ecobici.eval import saturation

# 09:00 CDMX on a Tuesday = 15:00 UTC.
T0 = datetime(2025, 3, 4, 15, 0, tzinfo=UTC)
# A and B ~110 m apart (walkable); C ~5 km away.
COORDS = {"A": (19.4300, -99.2000), "B": (19.4310, -99.2000), "C": (19.3850, -99.2000)}


def snapshot(t, full):
    return [
        {
            "station_id": s,
            "name": f"CE-{s}",
            "latitude": lat,
            "longitude": lon,
            "capacity": 20,
            "num_docks_available": 0 if s in full else 5,
            "is_installed": True,
            "is_returning": True,
            "committed_at_utc": t,
        }
        for s, (lat, lon) in COORDS.items()
    ]


@pytest.fixture
def con(tmp_path):
    rows = []
    # Four peak readings: A full in all, B full with A twice, C never full.
    for i, full in enumerate([{"A", "B"}, {"A", "B"}, {"A"}, {"A"}]):
        rows += snapshot(T0 + timedelta(minutes=15 * i), full)
    path = tmp_path / "2025-03.parquet"
    pl.DataFrame(rows).write_parquet(path)
    return saturation.connect([path])


def test_v1_peak_counts(con):
    r = saturation.v1(con)
    assert r["overall_full_rate"] == pytest.approx(6 / 12)
    assert r["peak_stations"] == 3
    assert r["peak_ge_50"] == 2  # A (100%) and B (50%)
    assert r["peak_top"][0][0] == "CE-A"


def test_v6_only_walkable_neighbours_count(con):
    r = saturation.v6(con)
    assert r["stations_with_neighbour"] == 2  # A and B; C is too far
    # Given A full (4 readings), B was full in 2; given B full (2), A was full in 2.
    assert r["p_b_full_given_a"] == pytest.approx(4 / 6)
    assert r["p_all_neighbours_full"] == pytest.approx(4 / 6)
    assert "V6" in saturation.format_report(saturation.v1(con), r)
