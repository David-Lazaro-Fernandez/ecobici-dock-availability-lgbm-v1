"""Data access for the dev station viewer: live feed or local raw captures."""

import gzip
import json
from pathlib import Path

import pandas as pd
import requests

from ecobici import config
from ecobici.collector.report import fetched_at
from ecobici.labels import classify

INFO_COLUMNS = ["station_id", "short_name", "name", "lat", "lon", "capacity"]
STATUS_COLUMNS = [
    "station_id",
    "num_docks_available",
    "num_docks_disabled",
    "num_bikes_available",
    "num_bikes_disabled",
    "is_installed",
    "is_returning",
    "last_reported",
]


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


def snapshot_frame(information: dict, status: dict) -> pd.DataFrame:
    """One row per station: location, capacity, current counts and label."""
    info = pd.DataFrame(information["data"]["stations"]).reindex(columns=INFO_COLUMNS)
    feed_updated = int(status["last_updated"])
    stations = status["data"]["stations"]
    st = pd.DataFrame(stations).reindex(columns=STATUS_COLUMNS)
    st["label"] = [str(classify(s, feed_updated)) for s in stations]
    st["minutes_since_report"] = (feed_updated - st["last_reported"]) / 60
    df = info.merge(st, on="station_id", how="inner")
    df.attrs["feed_updated"] = feed_updated  # epoch seconds; attrs must stay JSON-serialisable
    return df


def station_history(captures: list[Path], station_id: str) -> pd.DataFrame:
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
    return pd.DataFrame(rows, columns=["time", "docks_available", "bikes_available", "label"])
