"""The own captures as daily snapshot files in the MaxHalford schema (M7).

    uv run python -m ecobici.ingest.capture_snapshots   # After the S3 sync.

One file per UTC day: ``data/own/snapshots/YYYY-MM-DD.parquet``. ``targets.load_snapshots``
reads them like the MaxHalford files. Stale readings are removed: they must not become
labels. A day is built again only if its number of captures changed (``manifest.json``).

Capacity and coordinates come from the last station_information capture. They change
rarely, and the station list of the model comes from the MaxHalford months.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from ecobici.collector.report import fetched_at
from ecobici.devtools import stations as gbfs
from ecobici.live import capture_rows

DEFAULT_RAW = Path("raw")
DEFAULT_OUT = Path("data/own/snapshots")
MANIFEST = "manifest.json"


def captures_by_day(raw: Path) -> dict[str, list[Path]]:
    days: dict[str, list[Path]] = defaultdict(list)
    for path in gbfs.list_captures(raw):
        days[f"{fetched_at(path):%Y-%m-%d}"].append(path)
    return dict(days)


def build(raw: Path = DEFAULT_RAW, out: Path = DEFAULT_OUT, log=print) -> list[Path]:
    """Write the days with changed captures. Return all day files."""
    info = gbfs.latest_information(raw)
    if info is None:
        raise SystemExit(f"no station_information capture under {raw}/")
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / MANIFEST
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    days = captures_by_day(raw)
    for day, paths in sorted(days.items()):
        target = out / f"{day}.parquet"
        if manifest.get(day) == len(paths) and target.exists():
            continue
        rows = capture_rows(paths, info, drop_stale=True)
        tmp = target.with_suffix(".parquet.tmp")
        rows.write_parquet(tmp)
        tmp.replace(target)
        manifest[day] = len(paths)
        log(f"{day}: {len(paths)} captures, {rows.height:,} station readings")
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True))
    return sorted(out / f"{d}.parquet" for d in days)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    files = build(args.raw, args.out)
    print(f"{len(files)} days in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
