"""``ecobici-capture-report``: validation V2 over a local copy of raw captures.

Answers the M1 exit question: is the capture continuous enough to rebuild the
target? Reports minute coverage against the expected cadence, gaps, duplicate
feed snapshots, and the label mix (available / full / unavailable / stale).

Sync from S3 first, e.g. ``aws s3 sync s3://bucket/raw/station_status raw/station_status``.
"""

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ecobici import config
from ecobici.labels import classify

KEY_TS = re.compile(r"_(\d{8}T\d{6}Z)\.json\.gz$")


@dataclass
class Report:
    n_files: int = 0
    first: datetime | None = None
    last: datetime | None = None
    expected: int = 0
    gaps: list[tuple[datetime, datetime]] = field(default_factory=list)
    duplicate_snapshots: int = 0
    unreadable: int = 0
    labels: Counter = field(default_factory=Counter)

    @property
    def coverage(self) -> float:
        return self.n_files / self.expected if self.expected else 0.0


def fetched_at(path: Path) -> datetime:
    m = KEY_TS.search(path.name)
    if not m:
        raise ValueError(f"not a capture file: {path}")
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def build_report(
    root: Path,
    interval_s: int = config.CAPTURE_INTERVAL_SECONDS,
    gap_factor: float = 2.5,
) -> Report:
    files = sorted(root.rglob("station_status_*.json.gz"), key=fetched_at)
    rep = Report(n_files=len(files))
    if not files:
        return rep

    times = [fetched_at(f) for f in files]
    rep.first, rep.last = times[0], times[-1]
    rep.expected = int((rep.last - rep.first).total_seconds() // interval_s) + 1
    rep.gaps = [
        (a, b)
        for a, b in zip(times, times[1:], strict=False)
        if (b - a).total_seconds() > gap_factor * interval_s
    ]

    seen_updates: set[int] = set()
    for f in files:
        try:
            payload = json.loads(gzip.decompress(f.read_bytes()))
        except (OSError, ValueError):
            rep.unreadable += 1
            continue
        last_updated = int(payload["last_updated"])
        if last_updated in seen_updates:
            rep.duplicate_snapshots += 1
        seen_updates.add(last_updated)
        for station in payload["data"]["stations"]:
            rep.labels[classify(station, last_updated)] += 1
    return rep


def format_report(rep: Report) -> str:
    if not rep.n_files:
        return "No captures found."
    total = sum(rep.labels.values()) or 1
    lines = [
        f"Window:     {rep.first:%Y-%m-%d %H:%M} → {rep.last:%Y-%m-%d %H:%M} UTC",
        f"Captures:   {rep.n_files} of {rep.expected} expected ({rep.coverage:.1%})",
        f"Gaps:       {len(rep.gaps)}",
        *(
            f"  {a:%m-%d %H:%M} → {b:%m-%d %H:%M} ({(b - a).total_seconds() / 60:.0f} min)"
            for a, b in rep.gaps[:20]
        ),
        f"Duplicate feed snapshots (same last_updated): {rep.duplicate_snapshots}",
        f"Unreadable files: {rep.unreadable}",
        "Station readings by label:",
        *(f"  {label:<12} {n:>9}  {n / total:6.2%}" for label, n in rep.labels.most_common()),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path, help="Directory holding station_status captures")
    args = parser.parse_args(argv)
    print(format_report(build_report(args.root)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
