"""The plans that the web app asks for: one small JSON file for each plan.

The API writes each plan to ``ECOBICI_PLAN_SINK``: a local directory or
``s3://bucket/prefix``. Without it, the API saves no plans. The key is
``YYYY/MM/DD/<plan_id>.json.gz`` (local date of the capture). The web app makes ``plan_id``
once per search and sends the same id with the feedback, so a plan and its answers join on
it.

A plan holds the station ids, the predictions shown and how the person chose each end of the
trip. A public place (a station, a place in the index or a named place from Photon) keeps its
name and coordinates: they show the places to add to the search index. A street address, a
map point or the device location keeps no name and no coordinates. For those ends, the walk
distances become an order: distances to three stations give the exact point.
"""

import gzip
import json
import os
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Literal

from ecobici import config
from ecobici.collector.sinks import Sink, sink_from_uri

SINK_ENV = "ECOBICI_PLAN_SINK"
# The web app asks again for the same plan every minute. Keep the first answer only.
SEEN_MAX = 10_000

Kind = Literal["station", "index", "photon", "address", "map", "location"]
PUBLIC_KINDS = {"station", "index", "photon"}
# The distance fields of a pickup or a drop-off. With a private end, they go.
DISTANCE_FIELDS = ("walk_m", "walk_min", "total_min", "expected_min")


def default_sink() -> Sink | None:
    uri = os.environ.get(SINK_ENV)
    return sink_from_uri(uri) if uri else None


def key(plan_id: str, captured_at: datetime) -> str:
    day = captured_at.astimezone(config.LOCAL_TZ).strftime("%Y/%m/%d")
    return f"{day}/{plan_id}.json.gz"


def end(
    kind: Kind | None, name: str | None, osm: str | None, lat: float | None, lng: float | None
) -> dict:
    """One end of the trip. Only a public place keeps its name and its point. A start at a
    station has no point: the station id tells it."""
    if kind not in PUBLIC_KINDS:
        return {"kind": kind}
    point = {} if lat is None or lng is None else {"lat": round(lat, 5), "lng": round(lng, 5)}
    return {"kind": kind, "name": name, "osm": osm} | point


def by_walk_order(rows: list[dict], public: bool) -> list[dict]:
    """Add ``walk_order`` (1 = shortest walk). Without a public end, drop the distances."""
    order = sorted(range(len(rows)), key=lambda i: rows[i]["walk_m"])
    out = [dict(r, walk_order=order.index(i) + 1) for i, r in enumerate(rows)]
    if not public:
        out = [{k: v for k, v in r.items() if k not in DISTANCE_FIELDS} for r in out]
    return out


def write(sink: Sink, record: dict, captured_at: datetime) -> str:
    body = gzip.compress(json.dumps(record, ensure_ascii=False).encode())
    return sink.put(key(record["plan_id"], captured_at), body)


class Seen:
    """The plan ids saved by this process, at most ``limit``. Memory only."""

    def __init__(self, limit: int = SEEN_MAX):
        self.limit = limit
        self.ids: OrderedDict[str, None] = OrderedDict()
        self.lock = threading.Lock()

    def first(self, plan_id: str) -> bool:
        """True the first time for ``plan_id``."""
        with self.lock:
            if plan_id in self.ids:
                return False
            self.ids[plan_id] = None
            if len(self.ids) > self.limit:
                self.ids.popitem(last=False)
            return True
