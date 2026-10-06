"""Ecobici monthly trips (M4): discover, download, normalise to parquet, map to GBFS.

The open-data site lists one CSV per month under at least six naming schemes, split
across its English and Spanish pages (2025-02 only appears on the Spanish one). Files
are grouped by *arrival* month. Columns are stable except ``Fecha Arribo`` vs
``Fecha_Arribo``; quoting, zero-padding of station codes and age formatting vary.

Output, one parquet per month, keeps only what the model needs. Gender and age are
dropped at ingest (PRD privacy proposal). Times are local CDMX wall-clock.
"""

import argparse
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import requests

from ecobici import config

SITE = "https://ecobici.cdmx.gob.mx"
PAGES = (f"{SITE}/en/open-data/", f"{SITE}/datos-abiertos/")
DEFAULT_DIR = Path("data/external/trips")
FIRST_MONTH = "2022-08"  # new system only (PRD decision)

SPANISH_MONTHS = {
    m: i
    for i, m in enumerate(
        "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre "
        "diciembre".split(),
        start=1,
    )
}
NUMERIC = re.compile(r"(20\d{2})[-_](0[1-9]|1[0-2])(?!\d)")
NAMED = re.compile(r"(20\d{2})_(" + "|".join(SPANISH_MONTHS) + r")", re.IGNORECASE)
LINK = re.compile(r'href="([^"]+\.csv)"')

# Header spellings seen across months, after lower-casing and spaces → underscores.
COLUMN_ALIASES = {
    "bike_id": ("bici",),
    "origin_code": ("ciclo_estacion_retiro", "ce_retiro"),
    "origin_date": ("fecha_retiro",),
    "origin_time": ("hora_retiro",),
    "destination_code": ("ciclo_estacionarribo", "ciclo_estacion_arribo", "ce_arribo"),
    "destination_date": ("fecha_arribo",),
    "destination_time": ("hora_arribo",),
}


@dataclass(frozen=True)
class TripFile:
    month: str  # YYYY-MM of arrival
    url: str


def month_from_name(filename: str) -> str | None:
    if m := NUMERIC.search(filename):
        return f"{m.group(1)}-{m.group(2)}"
    if m := NAMED.search(filename):
        return f"{m.group(1)}-{SPANISH_MONTHS[m.group(2).lower()]:02d}"
    return None


def discover(session: requests.Session | None = None, first: str = FIRST_MONTH) -> list[TripFile]:
    """One file per month from both pages. When a month has several uploads, keep the
    most recent upload path (re-uploads like ``2025-10-1.csv`` replace the original)."""
    session = session or requests.Session()
    links: set[str] = set()
    for page in PAGES:
        resp = session.get(page, timeout=30)
        resp.raise_for_status()
        links |= set(LINK.findall(resp.text))
    by_month: dict[str, str] = {}
    for link in sorted(links):  # upload paths sort by /YYYY/MM/, so later wins
        month = month_from_name(link.rsplit("/", 1)[-1])
        if month and month >= first:
            by_month[month] = link if link.startswith("http") else SITE + link
    return [TripFile(m, u) for m, u in sorted(by_month.items())]


def _local_datetime(date_col: str, time_col: str) -> pl.Expr:
    """``dd/mm/yyyy`` or ``dd/mm/yy`` plus ``H:MM:SS`` → CDMX-aware datetime.

    The year width is chosen explicitly: parsing ``31/08/22`` with ``%Y`` would
    silently give year 22. Mexico's last DST change was 2022-10-30; that one
    ambiguous hour resolves to the earlier instant.
    """
    date = pl.col(date_col).str.strip_chars()
    time = pl.col(time_col).str.strip_chars().str.zfill(8)  # 0:00:27 → 00:00:27
    stamp = pl.concat_str(date, time, separator=" ")
    return (
        pl.when(date.str.contains(r"^\d{1,2}/\d{1,2}/\d{2}$"))
        .then(stamp.str.to_datetime("%d/%m/%y %H:%M:%S", strict=False))
        .otherwise(stamp.str.to_datetime("%d/%m/%Y %H:%M:%S", strict=False))
        .dt.replace_time_zone(config.LOCAL_TZ.key, ambiguous="earliest", non_existent="null")
    )


def _station_code(col: str) -> pl.Expr:
    """``64``, ``064`` and ``"064"`` → ``064``; paired codes like ``390-391`` kept as is."""
    c = pl.col(col).str.strip_chars().str.strip_chars('"')
    return pl.when(c.str.contains(r"^\d+$")).then(c.str.zfill(3)).otherwise(c)


def _canonical_columns(columns: list[str]) -> dict[str, str]:
    """Map each needed field to the file's actual header, or raise listing what's missing."""
    clean = {c.strip().lstrip("\ufeff").lower().replace(" ", "_"): c for c in columns}
    found, missing = {}, []
    for field, aliases in COLUMN_ALIASES.items():
        match = next((clean[a] for a in aliases if a in clean), None)
        if match is None:
            missing.append(field)
        else:
            found[match] = field
    if missing:
        raise ValueError(f"missing columns {missing}; header was {columns}")
    return found


def normalise(csv_path: Path) -> pl.DataFrame:
    raw = pl.read_csv(csv_path, infer_schema=False, encoding="utf8-lossy")
    rename = _canonical_columns(raw.columns)
    df = raw.select(list(rename)).rename(rename)
    return df.select(
        pl.col("bike_id").str.strip_chars(),
        _station_code("origin_code").alias("origin_code"),
        _station_code("destination_code").alias("destination_code"),
        _local_datetime("origin_date", "origin_time").alias("departed_at"),
        _local_datetime("destination_date", "destination_time").alias("arrived_at"),
    ).with_columns(
        duration_min=(pl.col("arrived_at") - pl.col("departed_at")).dt.total_seconds() / 60
    )


def _expected_size(resp: requests.Response, already: int) -> int | None:
    """Total file size from Content-Range (206) or Content-Length (200), if given."""
    if resp.status_code == 206:
        total = resp.headers.get("Content-Range", "").rpartition("/")[2]
        return int(total) if total.isdigit() else None
    length = resp.headers.get("Content-Length")
    return int(length) if length and length.isdigit() else None


def fetch_resumable(
    url: str,
    path: Path,
    session: requests.Session,
    attempts: int = 6,
    backoff_s: float = 30.0,
) -> None:
    """Download ``url`` into ``path``, resuming with HTTP Range after a stall or a cut.

    The open-data server periodically stalls every open connection at once; each retry
    waits longer (30 s, 60 s, …) and continues from the bytes already on disk instead of
    starting a 100+ MB file over.
    """
    for attempt in range(1, attempts + 1):
        have = path.stat().st_size if path.exists() else 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            with session.get(url, stream=True, timeout=(15, 60), headers=headers) as resp:
                if resp.status_code == 416:  # nothing left to send: already complete
                    return
                resp.raise_for_status()
                resumed = resp.status_code == 206
                expected = _expected_size(resp, have)
                with path.open("ab" if resumed else "wb") as fh:
                    for chunk in resp.iter_content(1 << 20):
                        fh.write(chunk)
            size = path.stat().st_size
            if expected is None or size >= expected:
                return
            raise requests.ConnectionError(f"short read: {size} of {expected} bytes")
        except requests.RequestException:
            if attempt == attempts:
                raise
            time.sleep(backoff_s * attempt)


def _fetch_month(f: TripFile, out: Path, session: requests.Session) -> int:
    """Download one month's CSV (resumable, kept under ``.partial/`` until done),
    normalise it and write the parquet atomically."""
    partial = out.parent / ".partial" / f"{f.month}.csv"
    partial.parent.mkdir(exist_ok=True)
    fetch_resumable(f.url, partial, session)
    df = normalise(partial).with_columns(source=pl.lit(f.url))
    df.write_parquet(out.with_suffix(".tmp"))
    out.with_suffix(".tmp").replace(out)
    partial.unlink()
    return df.height


def download(
    dest: Path = DEFAULT_DIR, session: requests.Session | None = None, workers: int = 3
) -> tuple[list[Path], dict[str, str]]:
    """Fetch and normalise every month not yet on disk; the CSV is discarded once its
    parquet is written. The server caps each connection at ~0.5 MB/s, so a few months run in
    parallel; keep ``workers`` small, it is a public site. A month that fails is reported
    and skipped so the rest still land. Returns (parquet paths, {month: error})."""
    session = session or requests.Session()
    dest.mkdir(parents=True, exist_ok=True)
    files = discover(session)
    todo = [f for f in files if not (dest / f"{f.month}.parquet").exists()]
    failed: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_fetch_month, f, dest / f"{f.month}.parquet", session): f for f in todo
        }
        for fut in as_completed(futures):
            f = futures[fut]
            try:
                print(f"{f.month}: {fut.result():,} trips", flush=True)
            except (requests.RequestException, ValueError, pl.exceptions.PolarsError) as exc:
                failed[f.month] = f"{f.url}: {exc}"
                print(f"{f.month}: FAILED {exc}", flush=True)
    paths = [dest / f"{f.month}.parquet" for f in files if f.month not in failed]
    return paths, failed


def station_code_map(information: dict) -> dict[str, str]:
    """Trip station code → GBFS ``station_id``. Paired stations (``390-391``) answer to
    either half and to the pair."""
    mapping = {}
    for s in information["data"]["stations"]:
        code = s["short_name"].strip()
        mapping[code] = s["station_id"]
        for part in code.split("-"):
            mapping.setdefault(part.zfill(3), s["station_id"])
    return mapping


def quality(root: Path, mapping: dict[str, str]) -> pl.DataFrame:
    """Per month: trips, unparseable times, plausible durations, and GBFS mapping rate."""
    known = list(mapping)
    return (
        pl.scan_parquet(root / "*.parquet", include_file_paths="path")
        .with_columns(month=pl.col("path").str.extract(r"(\d{4}-\d{2})\.parquet$"))
        .group_by("month")
        .agg(
            trips=pl.len(),
            bad_time=(pl.col("departed_at").is_null() | pl.col("arrived_at").is_null()).mean(),
            # Missing times count as implausible, not as absent.
            plausible=pl.col("duration_min").is_between(1, 180).fill_null(False).mean(),
            origin_mapped=pl.col("origin_code").is_in(known).mean(),
            destination_mapped=pl.col("destination_code").is_in(known).mean(),
        )
        .sort("month")
        .collect()
    )


def main(argv: list[str] | None = None) -> int:
    from ecobici.devtools.stations import fetch_live, latest_information

    parser = argparse.ArgumentParser(description="Ecobici monthly trips")
    parser.add_argument("command", choices=["list", "download", "quality"])
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--raw", type=Path, default=Path("raw"), help="Local GBFS captures")
    args = parser.parse_args(argv)

    if args.command == "list":
        files = discover()
        for f in files:
            print(f.month, f.url)
        print(f"{len(files)} months")
    elif args.command == "download":
        paths, failed = download(args.dir)
        print(f"{len(paths)} months in {args.dir}; {len(failed)} failed")
        for month, err in failed.items():
            print(f"  {month}: {err}")
        return 1 if failed else 0
    else:
        info = latest_information(args.raw) or fetch_live(config.STATION_INFORMATION_URL)
        with pl.Config(tbl_rows=-1, float_precision=3):
            print(quality(args.dir, station_code_map(info)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
