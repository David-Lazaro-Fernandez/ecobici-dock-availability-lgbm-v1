"""Anonymous feedback from the web app: one small JSON file for each answer.

The API writes each answer to ``ECOBICI_FEEDBACK_SINK``: a local directory (default
``data/feedback``) or ``s3://bucket/prefix``. The key is
``YYYY/MM/DD/<plan_id>_<kind>.json.gz`` (local date of the plan), so a second answer to
the same question replaces the first. The answers hold station ids, times, the
probabilities shown and the answer. No coordinates, addresses or IP addresses: they can
identify a person.
"""

import gzip
import json
import os
import threading
import time
from collections import deque
from datetime import datetime

from ecobici import config
from ecobici.collector.sinks import Sink, sink_from_uri

SINK_ENV = "ECOBICI_FEEDBACK_SINK"
DEFAULT_SINK = "data/feedback"


def default_sink() -> Sink:
    return sink_from_uri(os.environ.get(SINK_ENV, DEFAULT_SINK))


def key(plan_id: str, kind: str, captured_at: datetime) -> str:
    day = captured_at.astimezone(config.LOCAL_TZ).strftime("%Y/%m/%d")
    return f"{day}/{plan_id}_{kind}.json.gz"


def write(sink: Sink, record: dict, captured_at: datetime) -> str:
    body = gzip.compress(json.dumps(record, ensure_ascii=False).encode())
    return sink.put(key(record["plan_id"], record["kind"], captured_at), body)


class RateLimit:
    """At most ``limit`` calls per client in ``window_s`` seconds. Memory only: the client
    keys are not stored."""

    def __init__(self, limit: int, window_s: float):
        self.limit = limit
        self.window_s = window_s
        self.calls: dict[str, deque[float]] = {}
        self.lock = threading.Lock()

    def allow(self, client: str) -> bool:
        now = time.monotonic()
        with self.lock:
            # Drop idle clients so the table does not grow without limit.
            for c in [c for c, q in self.calls.items() if not q or q[-1] < now - self.window_s]:
                del self.calls[c]
            recent = self.calls.setdefault(client, deque())
            while recent and recent[0] < now - self.window_s:
                recent.popleft()
            if len(recent) >= self.limit:
                return False
            recent.append(now)
            return True
