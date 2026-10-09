"""Summarize route_pairs.py: engine time error against real rides, and the cost of bike_lanes.

    uv run python scripts/route_test/analyze.py [data/route_test/pairs.parquet]

Lane share = separated + painted lanes. Shared lanes (bus, pictogram) do not count.
"""

import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[2]
PAIRS = ROOT / "data" / "route_test" / "pairs.parquet"
ENGINES = (("OSRM (public)", "osrm"), ("GraphHopper bike_fast", "bike_fast"))
DISTANCE_BANDS_KM = ((0, 2), (2, 4), (4, 7), (7, 99))
MUCH_LONGER = 0.5
BIG_GAIN = 0.2
SAME_ROUTE_GAIN, SAME_ROUTE_EXTRA_MIN = 0.02, 0.5


def time_error(d: pl.DataFrame) -> None:
    print("== Engine minutes against the real median ride")
    for name, engine in ENGINES:
        minutes = d[f"{engine}_min"]
        err = (minutes - d["ride_min"]).abs()
        ratio = (minutes / d["ride_min"]).median()
        weighted = (err * d["trips"]).sum() / d["trips"].sum()
        # One constant speed correction, fitted on the same pairs: optimistic.
        corrected = (minutes / ratio - d["ride_min"]).abs().median()
        corr = d.select(pl.corr(f"{engine}_min", "ride_min")).item()
        print(f"{name}:")
        print(f"  median abs err {err.median():.1f} min, trip-weighted mean {weighted:.1f} min")
        print(f"  engine/real {ratio:.2f}, corr {corr:.3f}")
        print(f"  after one speed correction: median abs err {corrected:.1f} min")
    osrm_km, gh_km = d["osrm_km"].median(), d["bike_fast_km"].median()
    print(f"median km: OSRM {osrm_km:.2f}, GraphHopper {gh_km:.2f}")


def lane_share(d: pl.DataFrame, profile: str) -> pl.Series:
    return d[f"{profile}_separated_share"] + d[f"{profile}_painted_share"]


def lane_cost(d: pl.DataFrame) -> None:
    fast, lanes = lane_share(d, "bike_fast"), lane_share(d, "bike_lanes")
    gain = lanes - fast
    extra = d["bike_lanes_min"] - d["bike_fast_min"]
    longer = extra / d["bike_fast_min"]
    print("\n== bike_lanes against bike_fast (GraphHopper minutes)")
    print(f"lane share mean {fast.mean():.0%} -> {lanes.mean():.0%}")
    print(f"lane share median {fast.median():.0%} -> {lanes.median():.0%}")
    for lane in ("separated", "painted", "shared"):
        before = d[f"bike_fast_{lane}_share"].mean()
        after = d[f"bike_lanes_{lane}_share"].mean()
        print(f"  {lane} mean {before:.0%} -> {after:.0%}")
    p75, p90 = gain.quantile(0.75), gain.quantile(0.9)
    print(f"gain: median {gain.median():.0%}, p75 {p75:.0%}, p90 {p90:.0%}")
    print(
        f"extra min: median {extra.median():.1f}, p75 {extra.quantile(0.75):.1f}, "
        f"p90 {extra.quantile(0.9):.1f}, max {extra.max():.1f}"
    )
    print(f"extra %: median {longer.median():.0%}, p90 {longer.quantile(0.9):.0%}")
    print(f"pairs more than {MUCH_LONGER:.0%} longer: {(longer > MUCH_LONGER).mean():.0%}")
    same = (gain < SAME_ROUTE_GAIN) & (extra < SAME_ROUTE_EXTRA_MIN)
    print(f"same route: {same.mean():.0%}")
    big = gain >= BIG_GAIN
    big_extra = extra.filter(big).median()
    print(f"gain >= {BIG_GAIN:.0%}: {big.mean():.0%}, median extra {big_extra:.1f} min")
    for lo, hi in DISTANCE_BANDS_KM:
        m = d["crow_km"].is_between(lo, hi, closed="left")
        print(
            f"  crow {lo}-{hi} km: n={m.sum()}, lane share {fast.filter(m).mean():.0%} -> "
            f"{lanes.filter(m).mean():.0%}, extra median {extra.filter(m).median():.1f} min"
        )


def main(path: Path = PAIRS) -> int:
    d = pl.read_parquet(path).drop_nulls(["osrm_min", "bike_fast_min", "bike_lanes_min"])
    print(f"{len(d)} pairs, {d['trips'].sum():,} real trips")
    print(f"median real ride {d['ride_min'].median():.1f} min")
    print(f"median crow-fly {d['crow_km'].median():.2f} km\n")
    time_error(d)
    lane_cost(d)
    return 0


if __name__ == "__main__":
    sys.exit(main(*map(Path, sys.argv[1:2])))
