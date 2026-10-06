"""One capture of a GBFS feed: fetch, sanity-check, gzip the raw bytes, store.

Each run is a single shot; scheduling (every 2 min for station_status, daily for
station_information) lives in systemd timers under ``deploy/``. The bytes are stored
exactly as served so every derived dataset can be rebuilt from ``raw/``.
"""

import gzip
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import requests

from ecobici import config
from ecobici.collector.sinks import Sink

log = logging.getLogger(__name__)

FEEDS = {
    "station_status": config.STATION_STATUS_URL,
    "station_information": config.STATION_INFORMATION_URL,
    "system_information": config.SYSTEM_INFORMATION_URL,
}


class InvalidPayload(ValueError):
    pass


@dataclass(frozen=True)
class CaptureResult:
    feed: str
    location: str
    fetched_at: datetime
    feed_last_updated: int
    n_stations: int | None


def object_key(feed: str, fetched_at: datetime) -> str:
    """``<feed>/YYYY/MM/DD/<feed>_YYYYMMDDTHHMMSSZ.json.gz`` in UTC."""
    ts = fetched_at.astimezone(UTC)
    return f"{feed}/{ts:%Y/%m/%d}/{feed}_{ts:%Y%m%dT%H%M%SZ}.json.gz"


def validate(feed: str, body: bytes) -> tuple[int, int | None]:
    """Return ``(last_updated, n_stations)``; raise InvalidPayload on a bad body."""
    try:
        payload = json.loads(body)
        last_updated = int(payload["last_updated"])
        data = payload["data"]
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidPayload(f"{feed}: not a GBFS document ({exc})") from exc
    if "stations" not in data:
        return last_updated, None
    stations = data["stations"]
    if not isinstance(stations, list) or not stations:
        raise InvalidPayload(f"{feed}: empty or malformed station list")
    return last_updated, len(stations)


def fetch(url: str, session: requests.Session, attempts: int = 3, backoff_s: float = 5.0) -> bytes:
    for attempt in range(1, attempts + 1):
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            if attempt == attempts:
                raise
            log.warning("fetch %s failed (attempt %d/%d): %s", url, attempt, attempts, exc)
            time.sleep(backoff_s * attempt)
    raise AssertionError("unreachable")


def capture(feed: str, sink: Sink, session: requests.Session | None = None) -> CaptureResult:
    session = session or requests.Session()
    fetched_at = datetime.now(UTC)
    body = fetch(FEEDS[feed], session)
    last_updated, n_stations = validate(feed, body)
    location = sink.put(object_key(feed, fetched_at), gzip.compress(body))
    return CaptureResult(feed, location, fetched_at, last_updated, n_stations)
