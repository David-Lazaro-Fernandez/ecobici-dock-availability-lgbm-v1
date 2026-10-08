"""Data access for the dev station viewer: live feed or local raw captures."""

import gzip
import json
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import requests

from ecobici import config
from ecobici.collector.report import fetched_at
from ecobici.labels import classify

INFO_SCHEMA = {
    "station_id": pl.String,
    "short_name": pl.String,
    "name": pl.String,
    "lat": pl.Float64,
    "lon": pl.Float64,
    "capacity": pl.Int64,
}
STATUS_SCHEMA = {
    "station_id": pl.String,
    "num_docks_available": pl.Int64,
    "num_docks_disabled": pl.Int64,
    "num_bikes_available": pl.Int64,
    "num_bikes_disabled": pl.Int64,
    "is_installed": pl.Int64,
    "is_returning": pl.Int64,
    "last_reported": pl.Int64,
}
HISTORY_SCHEMA = {
    "time": pl.Datetime("us", config.LOCAL_TZ.key),
    "docks_available": pl.Int64,
    "bikes_available": pl.Int64,
    "label": pl.String,
}


@dataclass(frozen=True)
class Snapshot:
    stations: pl.DataFrame
    # Epoch seconds of the station_status document.
    feed_updated: int


def read_capture(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()))


def fetch_live(url: str) -> dict:
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return resp.json()


def list_captures(root: Path, feed: str = "station_status") -> list[Path]:
    return sorted((root / feed).rglob(f"{feed}_*.json.gz"), key=fetched_at)


def latest_information(root: Path) -> dict | None:
    files = list_captures(root, "station_information")
    return read_capture(files[-1]) if files else None


def frame(records: list[dict], schema: dict) -> pl.DataFrame:
    """Keep only the schema's columns; GBFS entries carry extra and sometimes missing keys."""
    return pl.DataFrame([{k: r.get(k) for k in schema} for r in records], schema=schema)


def snapshot_frame(information: dict, status: dict) -> Snapshot:
    """One row per station: location, capacity, current counts and label."""
    feed_updated = int(status["last_updated"])
    stations = status["data"]["stations"]
    st = frame(stations, STATUS_SCHEMA).with_columns(
        label=pl.Series([str(classify(s, feed_updated)) for s in stations], dtype=pl.String),
        minutes_since_report=(feed_updated - pl.col("last_reported")) / 60,
    )
    info = frame(information["data"]["stations"], INFO_SCHEMA)
    return Snapshot(info.join(st, on="station_id", how="inner"), feed_updated)


def station_history(captures: list[Path], station_id: str) -> pl.DataFrame:
    """Docks and bikes over time for one station across local captures."""
    rows = []
    for path in captures:
        payload = read_capture(path)
        feed_updated = int(payload["last_updated"])
        for s in payload["data"]["stations"]:
            if s["station_id"] == station_id:
                rows.append(
                    {
                        "time": fetched_at(path).astimezone(config.LOCAL_TZ),
                        "docks_available": s.get("num_docks_available"),
                        "bikes_available": s.get("num_bikes_available"),
                        "label": str(classify(s, feed_updated)),
                    }
                )
                break
    return pl.DataFrame(rows, schema=HISTORY_SCHEMA)
