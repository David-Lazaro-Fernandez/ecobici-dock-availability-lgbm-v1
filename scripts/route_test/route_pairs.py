"""Route a sample of dock pairs with GraphHopper (bike_fast, bike_lanes) and the public OSRM.

    uv run python scripts/route_test/route_pairs.py [--pairs 400]
    # writes data/route_test/pairs.parquet

Needs the GraphHopper of run_graphhopper.sh and the serving bundle (artifacts/serving).
The sample is fixed (seed): pairs with at least MIN_TRIPS real trips. OSRM is the free
FOSSGIS server, so the script waits OSRM_WAIT_S between pairs (~13 min for 400 pairs).
"""

import argparse
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "route_test" / "pairs.parquet"
BUNDLE = ROOT / "artifacts" / "serving"
GRAPHHOPPER = "http://127.0.0.1:8989/route"
OSRM = "https://routing.openstreetmap.de/routed-bike/route/v1/driving/"
USER_AGENT = "ecobici-dock-availability/0.1 (bike route test, 1 request/s)"
OSRM_WAIT_S = 1.0
MIN_TRIPS = 20
SEED = 7
# Some bundle stations have coordinates outside Mexico City (0,0 or Montreal).
LAT_RANGE, LON_RANGE = (19.0, 20.0), (-100.0, -98.0)
LANE_OF_NETWORK = {"international": "separated", "national": "painted", "regional": "shared"}
EARTH_M = 6_371_000


def meters(a: list[float], b: list[float]) -> float:
    """Great-circle distance between two [lon, lat] points."""
    lo1, la1, lo2, la2 = map(math.radians, (*a, *b))
    h = (
        math.sin((la2 - la1) / 2) ** 2
        + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    )
    return 2 * EARTH_M * math.asin(math.sqrt(h))


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def graphhopper(profile: str, o: tuple, d: tuple) -> dict:
    """Minutes, km and the share of the route on each lane class."""
    url = (
        f"{GRAPHHOPPER}?profile={profile}&point={o[0]},{o[1]}&point={d[0]},{d[1]}"
        "&points_encoded=false&instructions=false&details=mtb_network"
    )
    path = get_json(url)["paths"][0]
    pts = path["points"]["coordinates"]
    total = sum(meters(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) or 1.0
    on_lane = dict.fromkeys(LANE_OF_NETWORK.values(), 0.0)
    for start, end, network in path["details"]["mtb_network"]:
        lane = LANE_OF_NETWORK.get(str(network).lower())
        if lane:
            on_lane[lane] += sum(meters(pts[i], pts[i + 1]) for i in range(start, end))
    return {
        "min": path["time"] / 60_000,
        "km": path["distance"] / 1000,
        **{f"{lane}_share": m / total for lane, m in on_lane.items()},
    }


def osrm(o: tuple, d: tuple) -> dict:
    route = get_json(f"{OSRM}{o[1]},{o[0]};{d[1]},{d[0]}?overview=false")["routes"][0]
    return {"min": route["duration"] / 60, "km": route["distance"] / 1000}


def sample_pairs(n: int) -> tuple[pl.DataFrame, dict[str, tuple[float, float]]]:
    stations = pl.read_parquet(BUNDLE / "stations.parquet").filter(
        pl.col("lat").is_between(*LAT_RANGE) & pl.col("lon").is_between(*LON_RANGE)
    )
    where = {r["sid"]: (r["lat"], r["lon"]) for r in stations.iter_rows(named=True)}
    rides = pl.read_parquet(BUNDLE / "rides.parquet").filter(
        (pl.col("trips") >= MIN_TRIPS)
        & pl.col("origin_id").is_in(list(where))
        & pl.col("destination_id").is_in(list(where))
    )
    return rides.sample(n, seed=SEED), where


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pairs", type=int, default=400)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    pairs, where = sample_pairs(a.pairs)
    rows = []
    for i, r in enumerate(pairs.iter_rows(named=True)):
        o, d = where[r["origin_id"]], where[r["destination_id"]]
        row = {**r, "crow_km": meters([o[1], o[0]], [d[1], d[0]]) / 1000}
        for profile in ("bike_fast", "bike_lanes"):
            row |= {f"{profile}_{k}": v for k, v in graphhopper(profile, o, d).items()}
        try:
            row |= {f"osrm_{k}": v for k, v in osrm(o, d).items()}
        except OSError as e:
            print(f"OSRM failed for {r['origin_id']}->{r['destination_id']}: {e}", file=sys.stderr)
        rows.append(row)
        time.sleep(OSRM_WAIT_S)
        if (i + 1) % 50 == 0:
            print(f"{i + 1}/{len(pairs)}", file=sys.stderr)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(a.out)
    print(f"{a.out}: {len(rows)} pairs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
