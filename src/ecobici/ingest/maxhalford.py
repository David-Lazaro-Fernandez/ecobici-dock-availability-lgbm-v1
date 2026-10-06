"""MaxHalford/bike-sharing-history: download and diagnose the CDMX archive (M2, V4).

The archive is a set of monthly parquet files in a public GCS bucket, one full
snapshot of every station per git commit (~every 12 min when healthy). There is no
per-station ``last_reported``; ``committed_at_utc`` is the only timestamp.
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb
import requests

BUCKET_API = "https://storage.googleapis.com/storage/v1/b/bike-sharing-history/o"
OBJECT_URL = "https://storage.googleapis.com/bike-sharing-history/{name}"
PREFIX = "mexico-city/ecobici/"
DEFAULT_DIR = Path("data/external/maxhalford/mexico-city")

# Time is "covered" while consecutive snapshots are at most this far apart: the state
# is then known to within one 15-min slot either side. Slot counts are a bad measure
# here because the healthy cadence (~15.5 min) is itself about one slot.
MAX_COVERED_GAP_MIN = 30
# Informational only: training filters per example (snapshot near t and near t + h),
# so a partly covered month still contributes its covered stretches.
HEALTHY_TIME_COVERAGE = 0.80


@dataclass(frozen=True)
class RemoteFile:
    name: str
    size: int

    @property
    def month(self) -> str:
        """``mexico-city/ecobici/2025/Mar.parquet`` → ``2025-03``."""
        year, mon = self.name.removeprefix(PREFIX).removesuffix(".parquet").split("/")
        return datetime.strptime(f"{year} {mon}", "%Y %b").strftime("%Y-%m")


def list_remote(session: requests.Session | None = None) -> list[RemoteFile]:
    session = session or requests.Session()
    files, token = [], None
    while True:
        params = {"prefix": PREFIX, "fields": "items(name,size),nextPageToken"}
        if token:
            params["pageToken"] = token
        resp = session.get(BUCKET_API, params=params, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        files += [RemoteFile(i["name"], int(i["size"])) for i in body.get("items", [])]
        token = body.get("nextPageToken")
        if not token:
            return sorted(files, key=lambda f: f.month)


def download(dest: Path = DEFAULT_DIR, session: requests.Session | None = None) -> list[Path]:
    """Fetch every month not already present with the same size. Returns local paths."""
    session = session or requests.Session()
    dest.mkdir(parents=True, exist_ok=True)
    paths = []
    for f in list_remote(session):
        path = dest / f"{f.month}.parquet"
        if not (path.exists() and path.stat().st_size == f.size):
            resp = session.get(OBJECT_URL.format(name=f.name), timeout=120)
            resp.raise_for_status()
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(resp.content)
            tmp.replace(path)
        paths.append(path)
    return paths


def month_diagnostics(root: Path = DEFAULT_DIR) -> list[dict]:
    """Per month: snapshots, cadence, gaps, covered time, and usability."""
    glob = str(root / "*.parquet")
    sql = f"""
    WITH snaps AS (
        SELECT committed_at_utc AS t, count(*) AS stations
        FROM read_parquet('{glob}') GROUP BY t
    ),
    gaps AS (
        SELECT t, stations, strftime(t, '%Y-%m') AS month,
               epoch(t - lag(t) OVER (ORDER BY t)) / 60 AS gap_min
        FROM snaps
    )
    SELECT month,
           count(*) AS snapshots,
           round(median(stations)) AS stations,
           round(median(gap_min), 1) AS median_gap_min,
           round(quantile_cont(gap_min, 0.95), 1) AS p95_gap_min,
           count(*) FILTER (WHERE gap_min > 60) AS gaps_over_1h,
           round(max(gap_min) / 60, 1) AS max_gap_h,
           coalesce(sum(gap_min) FILTER (WHERE gap_min <= {MAX_COVERED_GAP_MIN}), 0)
               AS covered_min
    FROM gaps GROUP BY month ORDER BY month
    """
    with duckdb.connect() as con:
        con.execute("SET TimeZone='UTC'")
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    for r in rows:
        start = datetime.strptime(r["month"], "%Y-%m")
        days = (
            start.replace(year=start.year + start.month // 12, month=start.month % 12 + 1) - start
        ).days
        covered_min = r.pop("covered_min")
        r["covered_days"] = round(covered_min / (24 * 60), 1)
        r["time_coverage"] = round(covered_min / (days * 24 * 60), 3)
        r["healthy"] = r["time_coverage"] >= HEALTHY_TIME_COVERAGE
    return rows


def format_diagnostics(rows: list[dict]) -> str:
    head = (
        "| Month | Snapshots | Median gap (min) | p95 gap | Gaps >1 h | Max gap (h) "
        "| Covered days | Time covered | Healthy |"
    )
    sep = "|" + "---|" * 9
    body = [
        f"| {r['month']} | {r['snapshots']} | {r['median_gap_min']} | {r['p95_gap_min']} | "
        f"{r['gaps_over_1h']} | {r['max_gap_h']} | {r['covered_days']} | "
        f"{r['time_coverage']:.1%} | {'✅' if r['healthy'] else '❌'} |"
        for r in rows
    ]
    healthy = [r for r in rows if r["healthy"]]
    total = sum(r["covered_days"] for r in rows)
    return "\n".join(
        [
            head,
            sep,
            *body,
            "",
            f"Covered time, all months: {total:.0f} days",
            f"Healthy months (>= {HEALTHY_TIME_COVERAGE:.0%} covered): {len(healthy)}, "
            f"{sum(r['covered_days'] for r in healthy):.0f} covered days",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MaxHalford CDMX archive")
    parser.add_argument("command", choices=["download", "diagnose"])
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    if args.command == "download":
        paths = download(args.dir)
        print(f"{len(paths)} months in {args.dir}")
    else:
        print(format_diagnostics(month_diagnostics(args.dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
