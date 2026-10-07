"""Trip plan (PRD RF1–RF5, RF7, RF9): where to drop the bike near a destination.

Given a start station, a destination and the live predictions (ecobici.live):

- RF2 candidates: stations within ``radius_m`` estimated walking distance of the
  destination, and never fewer than ``min_candidates`` (best + backup).
- RF9 ride time to each candidate: the median of recent trips for that station pair
  when there are at least ``MIN_PAIR_TRIPS``, else distance / assumed speed.
- RF3 probability at *that candidate's* arrival time: P(full) interpolated between the
  model horizons (15 / 30 / 45 min), clamped outside them.
- RF4 score: expected minutes = ride + walk + P(full) × failure cost.
- RF7: out-of-service and stale stations are listed but never recommended.

Speeds and the walking detour are assumptions (PRD: "velocidades por definir").
"""

from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import polars as pl

from ecobici.eval.baseline_report import HORIZONS

BIKE_KMH = 12.0  # assumed riding speed, for pairs without enough trips
WALK_KMH = 4.8
DETOUR = 1.3  # street distance ≈ 1.3 × straight line
MIN_PAIR_TRIPS = 20
MAX_TRIP_MIN = 90  # longer trips are detours or errors, not rides between two stations
EARTH_M = 6_371_000


def distance_m(lat: pl.Expr, lon: pl.Expr, lat0: float, lon0: float) -> pl.Expr:
    """Great-circle distance to (lat0, lon0) in metres."""
    la, lo = lat.radians(), lon.radians()
    la0, lo0 = np.radians(lat0), np.radians(lon0)
    a = ((la - la0) / 2).sin() ** 2 + la.cos() * np.cos(la0) * ((lo - lo0) / 2).sin() ** 2
    return 2 * EARTH_M * a.sqrt().arcsin()


def ride_times(trips_dir: Path, code_to_id: dict[str, str], since: datetime) -> pl.DataFrame:
    """Median ride minutes and trip count per (origin_id, destination_id), from trips
    departing at or after ``since``."""
    glob = str(trips_dir / "*.parquet")
    by_code = duckdb.execute(
        f"""
        SELECT origin_code, destination_code, median(duration_min) AS ride_min,
               count(*) AS trips
        FROM read_parquet('{glob}')
        WHERE departed_at >= ? AND duration_min BETWEEN 1 AND {MAX_TRIP_MIN}
          AND origin_code <> destination_code
        GROUP BY ALL
        """,
        [since],
    ).pl()
    ids = pl.DataFrame(
        {"code": list(code_to_id), "station_id": list(code_to_id.values())},
        schema={"code": pl.String, "station_id": pl.String},
    )
    return (
        by_code.join(
            ids.rename({"code": "origin_code", "station_id": "origin_id"}), on="origin_code"
        )
        .join(
            ids.rename({"code": "destination_code", "station_id": "destination_id"}),
            on="destination_code",
        )
        # Paired codes (390-391) map to one station: keep the busiest code pair.
        .sort("trips", descending=True)
        .unique(["origin_id", "destination_id"], keep="first")
        .select("origin_id", "destination_id", "ride_min", "trips")
    )


def p_full_at(p: dict[int, pl.Expr], minutes: pl.Expr) -> pl.Expr:
    """P(full) at ``minutes`` after now: linear between the model horizons, the nearest
    horizon outside them."""
    hs = sorted(p)
    out = pl.when(minutes <= hs[0]).then(p[hs[0]])
    for lo, hi in zip(hs, hs[1:], strict=False):
        w = (minutes - lo) / (hi - lo)
        out = out.when(minutes <= hi).then(p[lo] * (1 - w) + p[hi] * w)
    return out.otherwise(p[hs[-1]])


def plan(
    stations: pl.DataFrame,
    origin_id: str,
    destination: tuple[float, float],
    rides: pl.DataFrame,
    radius_m: float = 500,
    failure_cost_min: float = 7.5,
    min_candidates: int = 2,
) -> pl.DataFrame:
    """Candidate stations near ``destination`` (lat, lon), best first.

    ``stations`` has one row per station: station_id, lat, lon, label and
    ``p_full_{h}`` for each model horizon (null when not predicted). Returns the
    candidates with walk, ride, arrival, P(full), P(free dock), expected minutes, a
    ``recommendable`` flag and ``rank`` (1 = best, null when not recommendable).
    """
    origin = stations.filter(pl.col("station_id") == origin_id)
    if origin.is_empty():
        raise ValueError(f"unknown origin station {origin_id}")
    o_lat, o_lon = origin.row(0, named=True)["lat"], origin.row(0, named=True)["lon"]
    d_lat, d_lon = destination
    walk_m = distance_m(pl.col("lat"), pl.col("lon"), d_lat, d_lon) * DETOUR
    ride_est = (
        distance_m(pl.col("lat"), pl.col("lon"), o_lat, o_lon) * DETOUR / (BIKE_KMH * 1000 / 60)
    )
    pair = rides.filter(pl.col("origin_id") == origin_id).select(
        pl.col("destination_id").alias("station_id"), "ride_min", "trips"
    )
    near = (
        stations.filter(pl.col("station_id") != origin_id)
        .with_columns(walk_m=walk_m)
        .sort("walk_m")
        .with_row_index("by_distance")
        .filter((pl.col("walk_m") <= radius_m) | (pl.col("by_distance") < min_candidates))
        .drop("by_distance")
        .join(pair, on="station_id", how="left")
    )
    historical = pl.col("trips").fill_null(0) >= MIN_PAIR_TRIPS
    p = {h: pl.col(f"p_full_{h}") for h in HORIZONS}
    out = near.with_columns(
        walk_min=pl.col("walk_m") / (WALK_KMH * 1000 / 60),
        ride_min=pl.when(historical).then(pl.col("ride_min")).otherwise(ride_est),
        ride_source=pl.when(historical)
        .then(pl.format("median of {} trips", pl.col("trips")))
        .otherwise(pl.lit(f"estimate at {BIKE_KMH:.0f} km/h")),
    ).with_columns(
        p_full=p_full_at(p, pl.col("ride_min")),
        outside_horizons=(pl.col("ride_min") < HORIZONS[0]) | (pl.col("ride_min") > HORIZONS[-1]),
    )
    out = out.with_columns(
        p_free=1 - pl.col("p_full"),
        expected_min=pl.col("ride_min") + pl.col("walk_min") + pl.col("p_full") * failure_cost_min,
        recommendable=pl.col("p_full").is_not_null() & pl.col("label").is_in(["available", "full"]),
    )
    ranked = (
        out.filter(pl.col("recommendable"))
        .sort("expected_min")
        .with_row_index("rank", offset=1)
        .select("station_id", pl.col("rank").cast(pl.Int64))
    )
    return out.join(ranked, on="station_id", how="left").sort(["rank", "walk_m"], nulls_last=True)


USABLE = ("available", "full")  # in service and reporting; "full" still lends bikes


def has_bike(row: dict) -> bool:
    """A bike can be taken there right now: in service, reporting, at least one bike."""
    return row.get("label") in USABLE and (row.get("num_bikes_available") or 0) > 0


def nearest_with_bike(stations: pl.DataFrame, point: tuple[float, float]) -> dict | None:
    """The closest in-service, non-stale station with a bike to take (RF1 from an
    address, or instead of an empty start station), with ``walk_m`` and ``walk_min``
    from ``point``; None if there is none."""
    lat, lon = point
    rows = (
        stations.filter(pl.col("label").is_in(USABLE) & (pl.col("num_bikes_available") > 0))
        .with_columns(walk_m=distance_m(pl.col("lat"), pl.col("lon"), lat, lon) * DETOUR)
        .sort("walk_m")
    )
    if rows.is_empty():
        return None
    r = rows.row(0, named=True)
    return {**r, "walk_min": r["walk_m"] / (WALK_KMH * 1000 / 60)}
