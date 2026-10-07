"""``ecobici-capture-report``: validation V2 over a local copy of raw captures.

Answers the M1 exit question: is the capture continuous enough to rebuild the
target? Reports minute coverage against the expected cadence, gaps, duplicate
feed snapshots, the label mix (available / full / unavailable / stale), and how long
in-service stations go without reporting (to set the ``stale`` threshold).

It also reports the coverage of each weekday morning (07:00–11:00 CDMX). Docks run out
in that window, and the short-horizon models need consecutive 2-min captures there.

Sync from S3 first, e.g. ``aws s3 sync s3://bucket/raw/station_status raw/station_status``.
"""

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from ecobici import config
from ecobici.labels import classify

KEY_TS = re.compile(r"_(\d{8}T\d{6}Z)\.json\.gz$")

# Upper bounds (minutes) of the silence buckets for in-service stations.
SILENCE_BUCKETS = ((30, "< 30 min"), (60, "30-60 min"), (180, "1-3 h"), (1440, "3-24 h"))
MORNING = (time(7), time(11))  # Local time.


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
    silence: Counter = field(default_factory=Counter)
    # Local weekday → (captures in the morning window, expected).
    mornings: dict[date, tuple[int, int]] = field(default_factory=dict)

    @property
    def coverage(self) -> float:
        return self.n_files / self.expected if self.expected else 0.0


def fetched_at(path: Path) -> datetime:
    m = KEY_TS.search(path.name)
    if not m:
        raise ValueError(f"not a capture file: {path}")
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def silence_bucket(station: dict, feed_last_updated: int) -> str:
    last_reported = station.get("last_reported")
    if last_reported is None:
        return "never"
    minutes = (feed_last_updated - last_reported) / 60
    return next((name for bound, name in SILENCE_BUCKETS if minutes < bound), "> 1 day")


def morning_coverage(times: list[datetime], interval_s: int) -> dict[date, tuple[int, int]]:
    """Captures and expected captures per weekday morning (MORNING, local time). Only
    the mornings fully between the first and the last capture count."""
    if not times:
        return {}
    tz = config.LOCAL_TZ
    expected = int(
        (
            datetime.combine(date.min, MORNING[1]) - datetime.combine(date.min, MORNING[0])
        ).total_seconds()
        // interval_s
    )
    local = [t.astimezone(tz) for t in times]
    out = {}
    day = local[0].date()
    while day <= local[-1].date():
        start = datetime.combine(day, MORNING[0], tz)
        end = datetime.combine(day, MORNING[1], tz)
        if day.weekday() < 5 and local[0] <= start and end <= local[-1]:
            out[day] = (sum(start <= t < end for t in local), expected)
        day += timedelta(days=1)
    return out


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

    rep.mornings = morning_coverage(times, interval_s)

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
            if station.get("is_installed") and station.get("is_returning"):
                rep.silence[silence_bucket(station, last_updated)] += 1
    return rep


def format_report(rep: Report) -> str:
    if not rep.n_files:
        return "No captures found."
    total = sum(rep.labels.values()) or 1
    silent_total = sum(rep.silence.values()) or 1
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
        "Weekday mornings (07:00–11:00 CDMX), captures of expected:",
        *(
            f"  {d:%a %Y-%m-%d}  {got:>4} of {exp}  ({got / exp:.0%})"
            + ("  ← gaps" if got < 0.95 * exp else "")
            for d, (got, exp) in sorted(rep.mornings.items())
        ),
        *([] if rep.mornings else ["  (no complete weekday morning yet)"]),
        "Station readings by label:",
        *(f"  {label:<12} {n:>9}  {n / total:6.2%}" for label, n in rep.labels.most_common()),
        "In-service readings by time since the station last reported:",
        *(
            f"  {name:<12} {rep.silence[name]:>9}  {rep.silence[name] / silent_total:6.2%}"
            for name in [*(n for _, n in SILENCE_BUCKETS), "> 1 day", "never"]
            if rep.silence[name]
        ),
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
