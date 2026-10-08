"""Station state labels (docs/ENG_PLAN.md finding 1).

A reading is classified from a GBFS station_status entry plus the feed's own
``last_updated`` timestamp:

- ``unavailable``: not installed or not accepting returns. Kept apart from ``full`` so
  outages are never mistaken for saturation, and excluded by the recommender (RF7).
  Checked first: out-of-service stations also stop reporting, and an old report of
  "not accepting returns" is still the best evidence we have.
- ``stale``: ``last_reported`` too old relative to the feed, so it carries no label and
  is not recommended. Stations report only on change, so the threshold is long enough
  for a quiet station (often one with no bikes, i.e. every dock free) to stay valid.
- ``full``: installed, accepting returns, and no free dock.
- ``available``: at least one free dock.
"""

from enum import StrEnum

from ecobici.config import STALE_AFTER_SECONDS


class StationState(StrEnum):
    AVAILABLE = "available"
    FULL = "full"
    UNAVAILABLE = "unavailable"
    STALE = "stale"


def classify(station: dict, feed_last_updated: int) -> StationState:
    if not station.get("is_installed") or not station.get("is_returning"):
        return StationState.UNAVAILABLE
    last_reported = station.get("last_reported")
    if last_reported is None or feed_last_updated - last_reported > STALE_AFTER_SECONDS:
        return StationState.STALE
    if station.get("num_docks_available", 0) == 0:
        return StationState.FULL
    return StationState.AVAILABLE


def is_recommendable(state: StationState) -> bool:
    """Only stations with a current, in-service reading can be recommended (RF7)."""
    return state in (StationState.AVAILABLE, StationState.FULL)
