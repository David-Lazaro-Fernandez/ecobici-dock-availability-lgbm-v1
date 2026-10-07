from datetime import datetime

import polars as pl
import pytest

from ecobici import config
from ecobici.recommender import plan as rp

# ~111 m per 0.001° of latitude. Destination at (19.400, -99.170).
DEST = (19.400, -99.170)


def stations(**over):
    base = {
        "station_id": ["O", "A", "B", "C", "F", "S"],
        "lat": [19.380, 19.4010, 19.4025, 19.4100, 19.4005, 19.4002],
        "lon": [-99.170] * 6,
        "label": ["available", "available", "available", "available", "unavailable", "stale"],
        "p_full_15": [0.0, 0.60, 0.10, 0.0, None, 0.0],
        "p_full_30": [0.0, 0.40, 0.20, 0.0, None, 0.0],
        "p_full_45": [0.0, 0.20, 0.30, 0.0, None, 0.0],
    }
    return pl.DataFrame({**base, **over})


RIDES = pl.DataFrame(
    {"origin_id": ["O"], "destination_id": ["B"], "ride_min": [30.0], "trips": [50]}
)


def test_distance_is_about_111_m_per_millidegree():
    d = pl.select(rp.distance_m(pl.lit(19.401), pl.lit(-99.17), *DEST)).item()
    assert d == pytest.approx(111.2, abs=0.5)


def test_interpolates_between_horizons_and_clamps_outside():
    p = {15: pl.lit(0.6), 30: pl.lit(0.4), 45: pl.lit(0.2)}
    got = pl.select(
        [rp.p_full_at(p, pl.lit(m)).alias(str(m)) for m in (5, 15, 22.5, 30, 40, 60)]
    ).row(0)
    assert got == pytest.approx((0.6, 0.6, 0.5, 0.4, 0.4 - 0.2 * 10 / 15, 0.2))


def test_plan_ranks_by_expected_time_and_excludes_out_of_service():
    out = rp.plan(stations(), "O", DEST, RIDES, radius_m=500, failure_cost_min=10)
    by = {r["station_id"]: r for r in out.to_dicts()}
    # C is ~1.4 km away on foot: out of the radius; the origin is never a candidate.
    assert set(by) == {"A", "B", "F", "S"}
    # B has a historical ride (30 min); A is estimated from distance (~2.3 km × 1.3).
    assert by["B"]["ride_min"] == 30 and by["B"]["ride_source"] == "median of 50 trips"
    assert by["A"]["ride_source"].startswith("estimate")
    assert by["A"]["ride_min"] == pytest.approx(2335 * 1.3 / 200, rel=0.01)
    # A arrives at ~15 min with P(full) ~0.6; B at 30 min with 0.2.
    assert by["A"]["p_full"] == pytest.approx(0.6, abs=0.02)
    assert by["B"]["p_full"] == pytest.approx(0.2)
    assert by["B"]["p_free"] == pytest.approx(0.8)
    # Out of service (no prediction) and stale: listed, never ranked.
    assert not by["F"]["recommendable"] and by["F"]["rank"] is None
    assert not by["S"]["recommendable"] and by["S"]["rank"] is None
    # Expected = ride + walk + P(full) × 10: A ≈ 15.2 + 1.8 + 6.0; B = 30 + 4.5 + 2.0.
    assert by["A"]["rank"] == 1 and by["B"]["rank"] == 2
    assert out["station_id"].to_list()[:2] == ["A", "B"]


def test_plan_always_offers_at_least_two_candidates():
    out = rp.plan(stations(), "O", DEST, RIDES, radius_m=50, min_candidates=2)
    assert out.height >= 2  # nothing within 50 m on foot, still the two nearest


def test_ride_times_use_recent_trips_and_map_codes(tmp_path):
    tz = config.LOCAL_TZ
    trips = pl.DataFrame(
        {
            "origin_code": ["001", "001", "001", "001", "002"],
            "destination_code": ["002", "002", "002", "001", "001"],
            "departed_at": [
                datetime(2026, 9, 1, 8, tzinfo=tz),
                datetime(2026, 9, 2, 8, tzinfo=tz),
                datetime(2024, 1, 1, 8, tzinfo=tz),  # too old
                datetime(2026, 9, 1, 8, tzinfo=tz),  # round trip, skipped
                datetime(2026, 9, 1, 8, tzinfo=tz),
            ],
            "duration_min": [10.0, 14.0, 99.0, 20.0, 200.0],  # 200: not a plain ride
        }
    )
    trips.write_parquet(tmp_path / "2026-09.parquet")
    got = rp.ride_times(tmp_path, {"001": "a", "002": "b"}, datetime(2025, 10, 1, tzinfo=tz))
    assert got.to_dicts() == [
        {"origin_id": "a", "destination_id": "b", "ride_min": 12.0, "trips": 2}
    ]


def test_nearest_with_bike_skips_empty_and_out_of_service():
    df = stations(num_bikes_available=[5, 0, 3, 2, 9, 9])
    # A (no bikes), F (out of service) and S (stale) are closer, but B is the first usable.
    r = rp.nearest_with_bike(df, DEST)
    assert r["station_id"] == "B"
    assert r["walk_m"] == pytest.approx(2.5 * 111.2 * 1.3, rel=0.01)
    assert r["walk_min"] == pytest.approx(r["walk_m"] / 80)
    assert rp.nearest_with_bike(df.with_columns(num_bikes_available=pl.lit(0)), DEST) is None


def test_p_empty_rises_with_the_walk_and_caps_at_the_model_horizon():
    got = pl.select(
        [rp.p_empty_at(pl.lit(0.6), pl.lit(m)).alias(str(m)) for m in (0, 5, 15, 30)]
    ).row(0)
    assert got == pytest.approx((0.0, 0.2, 0.6, 0.6))


def test_pickup_options_have_bikes_and_carry_p_empty():
    df = stations(num_bikes_available=[5, 0, 3, 2, 9, 9], p_empty_15=[0.1, 0.0, 0.3, 0.2, 0.0, 0.0])
    opts = rp.pickup_options(df, DEST, radius_m=1500)
    # A has no bike, F is out of service and S is stale; O is 2.9 km away on foot.
    assert opts["station_id"].to_list() == ["B", "C"]
    b = opts.row(0, named=True)
    assert b["p_empty"] == pytest.approx(0.3 * b["walk_min"] / 15)
    # Nothing within the radius: still the nearest one.
    assert rp.pickup_options(df, DEST, radius_m=10)["station_id"].to_list() == ["B"]


def test_plan_reads_p_full_after_the_walk_to_the_pickup():
    early = rp.plan(stations(), "O", DEST, RIDES).filter(pl.col("station_id") == "B")
    late = rp.plan(stations(), "O", DEST, RIDES, depart_after_min=10).filter(
        pl.col("station_id") == "B"
    )
    # B: ride 30 → P(full) 0.2; with a 10-min walk first, arrival at 40, between the 30
    # (0.2) and 45 (0.3) min models → 0.2 + 10/15 × 0.1.
    assert early["p_full"][0] == pytest.approx(0.2)
    assert late["p_full"][0] == pytest.approx(0.2 + 10 / 15 * 0.1)
