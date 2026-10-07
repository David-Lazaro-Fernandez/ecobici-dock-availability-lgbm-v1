"""Address search for the trip planner (PRD RF1: start or destination as coordinates).

Uses OpenStreetMap's Nominatim, limited to a box around the Ecobici service area.
Its usage policy asks for an identifying User-Agent, at most one request per second
and cached results: the app only calls it when an address is typed, and caches it.
"""

from dataclasses import dataclass

import requests

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ecobici-dock-availability-dev/0.1 (local dev viewer)"
MARGIN_DEG = 0.02  # ~2 km around the outermost stations


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
