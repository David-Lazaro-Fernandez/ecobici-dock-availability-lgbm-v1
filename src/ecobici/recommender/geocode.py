"""Address search for the trip planner (PRD RF1), with OpenStreetMap Nominatim.

The search is limited to a box around the Ecobici stations. The Nominatim usage policy
requires a User-Agent that identifies the app, one request per second or less, and
cached results.
"""

from dataclasses import dataclass

import requests

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ecobici-dock-availability-dev/0.1 (local dev viewer)"
# ~2 km around the outermost stations.
MARGIN_DEG = 0.02


@dataclass(frozen=True)
class Place:
    name: str
    lat: float
    lon: float


def viewbox(lats: list[float], lons: list[float], margin: float = MARGIN_DEG) -> str:
    """Nominatim ``viewbox`` (left, top, right, bottom) around the stations."""
    return f"{min(lons) - margin},{max(lats) + margin},{max(lons) + margin},{min(lats) - margin}"


def search(
    query: str, box: str, limit: int = 5, session: requests.Session | None = None
) -> list[Place]:
    """Places matching ``query`` inside ``box``, best match first."""
    query = query.strip()
    if not query:
        return []
    resp = (session or requests).get(
        NOMINATIM,
        params={
            "q": query,
            "format": "jsonv2",
            "limit": limit,
            "countrycodes": "mx",
            "viewbox": box,
            "bounded": 1,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    resp.raise_for_status()
    return [Place(r["display_name"], float(r["lat"]), float(r["lon"])) for r in resp.json()]
