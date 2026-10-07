"""Export the index of places in the Ecobici area for instant suggestions in the web app.

    uv run python scripts/export_places.py    # writes web/public/lugares.json

Adapted from a-donde-ir (absolut-cinema): the same format, a box around the Ecobici
stations, and more kinds of destination (named buildings, museums, parks, hospitals).
Data from OpenStreetMap through the Overpass API (ODbL; the map shows the credit).

Run it by hand and commit the file: one query gives ~5,000 places. If Overpass fails,
the old file stays and the script exits 0. Without a file, the page suggests stations
and online results only. Standard library only.

Format (version 1): generated_at, source, kinds [label], places [[name, kind, lat, lng]].
``kinds`` is in priority order: with the same match, a lower kind comes first.
"""

import argparse
import json
import math
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "web" / "public" / "lugares.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "ecobici-dock-availability/0.1 (places index for the web app)"
# South, west, north, east: the Ecobici stations plus ~1 km.
BOX = (19.334, -99.223, 19.481, -99.121)
TIMEOUT_S = 120
# Same name and kind at this distance or less: one place.
SAME_PLACE_M = 400
KINDS = [
    "Alcaldía",
    "Colonia",
    "Metro",
    "Metrobús",
    "Tren ligero",
    "Estación",
    "Museo",
    "Lugar turístico",
    "Monumento",
    "Parque",
    "Plaza comercial",
    "Universidad",
    "Hospital",
    "Teatro",
    "Biblioteca",
    "Edificio",
]
_QUERY = """[out:json][timeout:{timeout}];
(
  nwr["place"~"^(borough|suburb|neighbourhood|quarter)$"]["name"]({box});
  nwr["public_transport"="station"]["name"]({box});
  nwr["public_transport"="platform"]["network"~"metrob",i]["name"]({box});
  nwr["tourism"~"^(museum|gallery|attraction)$"]["name"]({box});
  nwr["historic"="monument"]["name"]({box});
  nwr["leisure"="park"]["name"]({box});
  nwr["shop"="mall"]["name"]({box});
  nwr["amenity"~"^(university|college|hospital|theatre|library)$"]["name"]({box});
  nwr["building"]["name"]({box});
);
out tags center;"""


def kind_of(tags: dict) -> str | None:
    """The KINDS label of an OSM element, or None. The first matching rule wins: a museum
    in a named building is a museum."""
    place = tags.get("place")
    if place == "borough":
        return "Alcaldía"
    if place in ("suburb", "neighbourhood", "quarter"):
        return "Colonia"
    if tags.get("public_transport") in ("station", "platform"):
        text = " ".join(
            tags.get(k, "") for k in ("network", "operator", "station", "railway")
        ).lower()
        for word, kind in (
            ("metrobús", "Metrobús"),
            ("metrobus", "Metrobús"),
            ("light_rail", "Tren ligero"),
            ("tren ligero", "Tren ligero"),
            ("subway", "Metro"),
            ("stc", "Metro"),
        ):
            if word in text:
                return kind
        return "Estación"
    if tags.get("tourism") in ("museum", "gallery"):
        return "Museo"
    if tags.get("historic") == "monument":
        return "Monumento"
    if tags.get("tourism") == "attraction":
        return "Lugar turístico"
    if tags.get("leisure") == "park":
        return "Parque"
    if tags.get("shop") == "mall":
        return "Plaza comercial"
    amenity = {"university": "Universidad", "college": "Universidad", "hospital": "Hospital"}
    amenity |= {"theatre": "Teatro", "library": "Biblioteca"}
    if tags.get("amenity") in amenity:
        return amenity[tags["amenity"]]
    if "building" in tags:
        return "Edificio"
    return None


def _meters(a: tuple[float, float], b: tuple[float, float]) -> float:
    dlat = (a[0] - b[0]) * 111_320
    dlng = (a[1] - b[1]) * 111_320 * math.cos(math.radians(a[0]))
    return math.hypot(dlat, dlng)


def places(elements: list[dict]) -> list[list]:
    """[[name, kind, lat, lng]] without repeats: one station brings a node, platforms and
    a building with the same name."""
    kind_ix = {k: i for i, k in enumerate(KINDS)}
    kept: dict[tuple[str, str], list[tuple[float, float]]] = {}
    names: dict[tuple[str, str], str] = {}
    for e in elements:
        tags = e.get("tags", {})
        kind = kind_of(tags)
        center = e.get("center", {})
        where = (e["lat"], e["lon"]) if "lat" in e else (center.get("lat"), center.get("lon"))
        if not kind or where[0] is None:
            continue
        # People search the common name: "Ángel de la Independencia" is an alt_name.
        aliases = [n.strip() for k in ("name", "alt_name") for n in (tags.get(k) or "").split(";")]
        for name in filter(None, aliases):
            key = (name.lower(), kind)
            names.setdefault(key, name)
            same = kept.setdefault(key, [])
            if all(_meters(where, p) > SAME_PLACE_M for p in same):
                same.append(where)
    out = [
        [names[key], kind_ix[key[1]], round(lat, 5), round(lng, 5)]
        for key, points in kept.items()
        for lat, lng in points
    ]
    return sorted(out, key=lambda p: (p[1], p[0], p[2], p[3]))


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
        found = places(fetch())
    except (OSError, ValueError, KeyError) as e:
        kept = "the old file stays" if a.out.exists() else "the page uses online results only"
        print(f"Overpass failed ({e}); {kept}.", file=sys.stderr)
        return 0
    data = {
        "version": 1,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "© OpenStreetMap (ODbL)",
        "kinds": KINDS,
        "places": found,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{a.out}: {len(found)} places, {a.out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
