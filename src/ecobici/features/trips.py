"""Trip-derived features (M4): historical net flow per station and slot, and trip
duration per station pair and hour.

Both are *historical averages*, so they must be fitted on the training window only
(``start``/``end``) and then joined onto later periods; fitting them on the whole
history would leak the future into validation and test.
"""

from datetime import datetime
from pathlib import Path

import polars as pl

from ecobici.ingest.trips import DEFAULT_DIR

SLOT_MINUTES = 15
# Plausible trips (M4 quality check).
MIN_DURATION, MAX_DURATION = 1.0, 180.0


def load(
    start: datetime,
    end: datetime,
    mapping: dict[str, str],
    root: Path = DEFAULT_DIR,
) -> pl.LazyFrame:
    """Plausible trips that *arrive* in [start, end), mapped to GBFS station ids."""
    codes = pl.DataFrame(
        {"code": list(mapping), "station_id": list(mapping.values())},
        schema={"code": pl.String, "station_id": pl.String},
    ).lazy()
    return (
        pl.scan_parquet(root / "*.parquet")
        .filter(
            pl.col("arrived_at").is_between(start, end, closed="left"),
            pl.col("duration_min").is_between(MIN_DURATION, MAX_DURATION),
        )
        .join(codes.rename({"station_id": "origin_id"}), left_on="origin_code", right_on="code")
        .join(
            codes.rename({"station_id": "destination_id"}),
            left_on="destination_code",
            right_on="code",
        )
    )


def _slot(col: str) -> pl.Expr:
    t = pl.col(col)
    return (t.dt.hour().cast(pl.Int32) * 60 + t.dt.minute()) // SLOT_MINUTES


def net_flow(trips: pl.LazyFrame) -> pl.DataFrame:
    """Mean arrivals, departures and net flow (arrivals − departures) per station,
    15-min slot of the day and day type, averaged over the days in the window.

    Positive net flow means the station tends to fill in that slot.
    """
    arrivals = trips.select(
        station_id="destination_id",
        day=pl.col("arrived_at").dt.date(),
        slot=_slot("arrived_at"),
        arrivals=pl.lit(1),
        departures=pl.lit(0),
    )
    departures = trips.select(
        station_id="origin_id",
        day=pl.col("departed_at").dt.date(),
        slot=_slot("departed_at"),
        arrivals=pl.lit(0),
        departures=pl.lit(1),
    )
    events = pl.concat([arrivals, departures]).with_columns(weekend=pl.col("day").dt.weekday() >= 6)
    # Divide by the number of days of that type in the window, not by the days a
    # station happened to have trips, so quiet stations are not inflated.
    days = events.select("day", "weekend").unique().group_by("weekend").agg(n_days=pl.len())
    return (
        events.group_by("station_id", "slot", "weekend")
        .agg(pl.col("arrivals").sum(), pl.col("departures").sum())
        .join(days, on="weekend")
        .select(
            "station_id",
            "slot",
            "weekend",
            arrivals_mean=pl.col("arrivals") / pl.col("n_days"),
            departures_mean=pl.col("departures") / pl.col("n_days"),
            net_flow_mean=(pl.col("arrivals") - pl.col("departures")) / pl.col("n_days"),
        )
        .sort("station_id", "weekend", "slot")
        .collect()
    )


def pair_duration(trips: pl.LazyFrame, min_trips: int = 5) -> pl.DataFrame:
    """Median and p75 trip minutes per (origin, destination, departure hour).

    Pairs with fewer than ``min_trips`` are dropped; callers fall back to a
    distance-based estimate (RF9) for those.
    """
    return (
        trips.filter(pl.col("origin_id") != pl.col("destination_id"))
        .group_by("origin_id", "destination_id", hour=pl.col("departed_at").dt.hour())
        .agg(
            n_trips=pl.len(),
            duration_median=pl.col("duration_min").median(),
            duration_p75=pl.col("duration_min").quantile(0.75, interpolation="linear"),
        )
        .filter(pl.col("n_trips") >= min_trips)
        .sort("origin_id", "destination_id", "hour")
        .collect()
    )
