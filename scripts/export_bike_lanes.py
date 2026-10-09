"""Export the bike lanes in the Ecobici area as a map layer for the web app.

    uv run python scripts/export_bike_lanes.py    # writes web/public/ciclovias.geojson

Data from OpenStreetMap through the Overpass API (ODbL; the map shows the credit). The lane
classes come from ecobici.bike_lanes, the same rules as the route test.

Run it by hand and commit the file. If Overpass fails, the old file stays and the script
exits 0. Without a file, the map has no bike-lane layer.

Format: a GeoJSON FeatureCollection of LineStrings. Each feature has one property,
``class``: separated, painted or shared.
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from ecobici.bike_lanes import lane_class

OUT = Path(__file__).resolve().parent.parent / "web" / "public" / "ciclovias.geojson"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "ecobici-dock-availability/0.1 (bike-lane layer for the web app)"
# South, west, north, east: the Ecobici stations plus ~1 km. Keep equal to export_places.py.
BOX = (19.334, -99.223, 19.481, -99.121)
TIMEOUT_S = 120
# 5 decimals is ~1 m: enough for a line on the map, and a smaller file.
DECIMALS = 5
_QUERY = """[out:json][timeout:{timeout}];
(
  way["highway"="cycleway"]({box});
  way["highway"="path"]["bicycle"="designated"]({box});
  way[~"^cycleway(:(left|right|both))?$"~"."]({box});
);
out tags geom;"""


def features(elements: list[dict]) -> list[dict]:
    """GeoJSON lines of the ways with a lane class, in a stable order for small diffs."""
    out = []
    for e in sorted(elements, key=lambda e: e["id"]):
        cls = lane_class(e.get("tags", {}))
        geometry = e.get("geometry") or []
        if e.get("type") != "way" or not cls or len(geometry) < 2:
            continue
        coords = [[round(p["lon"], DECIMALS), round(p["lat"], DECIMALS)] for p in geometry]
        out.append(
            {
                "type": "Feature",
                "properties": {"class": cls},
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )
    return out


def fetch() -> list[dict]:
    query = _QUERY.format(timeout=TIMEOUT_S, box=",".join(str(v) for v in BOX))
    body = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(OVERPASS_URL, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S + 30) as res:
        return json.load(res)["elements"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    try:
        found = features(fetch())
    except (OSError, ValueError, KeyError) as e:
        kept = "the old file stays" if a.out.exists() else "the map has no bike-lane layer"
        print(f"Overpass failed ({e}); {kept}.", file=sys.stderr)
        return 0
    data = {"type": "FeatureCollection", "features": found}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    counts = {
        c: sum(f["properties"]["class"] == c for f in found)
        for c in ("separated", "painted", "shared")
    }
    print(f"{a.out}: {len(found)} ways {counts}, {a.out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
