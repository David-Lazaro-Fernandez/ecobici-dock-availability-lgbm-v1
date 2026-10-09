"""Send concurrent route requests to the GraphHopper of run_graphhopper.sh (1 CPU).

    uv run python scripts/route_test/load_test.py

Prints routes per second and latency for each number of concurrent clients. The clients
run on the same machine, so they use some CPU too.
"""

import random
import statistics
import sys
import threading
import time
import urllib.request
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[2]
GRAPHHOPPER = "http://127.0.0.1:8989/route"
SECONDS_PER_LEVEL = 15
CLIENTS = (1, 4, 16, 32)
LAT_RANGE, LON_RANGE = (19.0, 20.0), (-100.0, -98.0)


def client(stations: list[tuple], latencies: list[float], stop: threading.Event, seed: int):
    rnd = random.Random(seed)
    while not stop.is_set():
        o, d = rnd.sample(stations, 2)
        profile = rnd.choice(["bike_fast", "bike_lanes"])
        url = (
            f"{GRAPHHOPPER}?profile={profile}&point={o[0]},{o[1]}&point={d[0]},{d[1]}"
            "&points_encoded=false&instructions=false&details=mtb_network"
        )
        started = time.perf_counter()
        urllib.request.urlopen(url).read()
        latencies.append((time.perf_counter() - started) * 1000)


def main() -> int:
    stations = pl.read_parquet(ROOT / "artifacts" / "serving" / "stations.parquet").filter(
        pl.col("lat").is_between(*LAT_RANGE) & pl.col("lon").is_between(*LON_RANGE)
    )
    points = list(zip(stations["lat"], stations["lon"], strict=True))
    for n in CLIENTS:
        latencies: list[float] = []
        stop = threading.Event()
        threads = [
            threading.Thread(target=client, args=(points, latencies, stop, i)) for i in range(n)
        ]
        for t in threads:
            t.start()
        time.sleep(SECONDS_PER_LEVEL)
        stop.set()
        for t in threads:
            t.join()
        q = statistics.quantiles(latencies, n=100)
        print(
            f"clients={n:3} routes/s={len(latencies) / SECONDS_PER_LEVEL:6.0f} "
            f"p50={q[49]:5.1f} ms p95={q[94]:5.1f} ms max={max(latencies):5.0f} ms"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
