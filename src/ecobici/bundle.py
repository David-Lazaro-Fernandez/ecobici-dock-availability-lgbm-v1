"""The serving bundle: the small tables the live service needs, built once from history.

    uv run --extra api python -m ecobici.bundle     # writes artifacts/serving/

The live service reads the bundle, not the history (~17 months of snapshots and ~1 GB
of trips). Thus it runs in ~0.7 GB of memory instead of ~7 GB. The tables come from the
same functions as training, so the predictions do not change. Build the bundle again
after a new model, a new month of trips, or a station change.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import polars as pl

from ecobici import config, live
from ecobici.devtools import stations as gbfs
from ecobici.eval.baseline_report import HORIZONS
from ecobici.eval.model_report import trip_flow
from ecobici.features import model_matrix, targets
from ecobici.ingest import trips as trip_ingest
from ecobici.recommender import plan as rp

BUNDLE_DIR = Path("artifacts/serving")
RIDE_HISTORY = timedelta(days=365)
# The horizons with a frozen model, per target.
MODEL_HORIZONS = {"full": HORIZONS, "empty": (rp.EMPTY_HORIZON,)}
NO_WEATHER = pl.DataFrame(
    schema={
        "time_utc": pl.Datetime("us", "UTC"),
        "temperature_2m": pl.Float64,
        "precipitation": pl.Float64,
    }
)


@dataclass(frozen=True)
class Bundle:
    stations: pl.DataFrame
    flow: pl.DataFrame
    rides: pl.DataFrame
    st_profile: dict[str, pl.DataFrame]
    # Target → horizon → saturated station ids.
    saturated: dict[str, dict[int, list[str]]]

    def save(self, out: Path, built_with: dict) -> None:
        out.mkdir(parents=True, exist_ok=True)
        self.stations.write_parquet(out / "stations.parquet")
        self.flow.write_parquet(out / "flow.parquet")
        self.rides.write_parquet(out / "rides.parquet")
        for target, profile in self.st_profile.items():
            profile.write_parquet(out / f"st_profile_{target}.parquet")
        (out / "saturated.json").write_text(json.dumps(self.saturated, indent=1))
        (out / "manifest.json").write_text(json.dumps(built_with, indent=1))


def load(path: Path = BUNDLE_DIR) -> Bundle:
    saturated = json.loads((path / "saturated.json").read_text())
    return Bundle(
        stations=pl.read_parquet(path / "stations.parquet"),
        flow=pl.read_parquet(path / "flow.parquet"),
        rides=pl.read_parquet(path / "rides.parquet"),
        st_profile={t: pl.read_parquet(path / f"st_profile_{t}.parquet") for t in saturated},
        # JSON keys are strings; the horizons are ints.
        saturated={t: {int(h): ids for h, ids in by_h.items()} for t, by_h in saturated.items()},
    )


def build(raw: Path = Path("raw"), trips_dir: Path = trip_ingest.DEFAULT_DIR) -> Bundle:
    files = live.model_files()
    flow = trip_flow(trips_dir, raw)
    info = gbfs.latest_information(raw) or gbfs.fetch_live(config.STATION_INFORMATION_URL)
    since = datetime.now(config.LOCAL_TZ) - RIDE_HISTORY
    rides = rp.ride_times(trips_dir, trip_ingest.station_code_map(info), since)
    stations, profiles, saturated = None, {}, {}
    for target, horizons in MODEL_HORIZONS.items():
        con = duckdb.connect(config={"memory_limit": "6GB"})
        targets.load_snapshots(con, files, target=target)
        model_matrix.prepare_shared(con, flow, NO_WEATHER, station_files=live.MODEL_FILES)
        stations = con.sql("SELECT sid, lat, lon, station FROM stations ORDER BY station").pl()
        profiles[target] = con.sql("SELECT * FROM st_profile ORDER BY sid").pl()
        saturated[target] = live.saturated_by_horizon(files, horizons, target=target)
        con.close()
    return Bundle(stations, flow, rides, profiles, saturated)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=BUNDLE_DIR)
    parser.add_argument("--raw", type=Path, default=Path("raw"))
    args = parser.parse_args(argv)
    bundle = build(args.raw)
    bundle.save(
        args.out,
        {
            "built_at": datetime.now(config.LOCAL_TZ).isoformat(timespec="seconds"),
            "model_files": list(live.MODEL_FILES),
            "ride_history_days": RIDE_HISTORY.days,
        },
    )
    sizes = ", ".join(f"{f.name} {f.stat().st_size // 1024} KB" for f in sorted(args.out.iterdir()))
    print(f"{args.out}: {sizes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
