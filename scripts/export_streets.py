"""Export the streets and the house numbers of the Ecobici area for the address search.

    uv run python scripts/export_streets.py    # writes web/public/calles.json and numeros.json

Streets: "Vialidades de la Ciudad de México" (INEGI, Marco Geoestadístico 2020,
CC-BY-4.0-ESP) from datos.cdmx.gob.mx. It has names and lines, with no house numbers.
House numbers: DENUE of Ciudad de México (INEGI, open data). Each establishment has a street,
an exterior number and a point. One point for each address: "Calle Durango 49" has
dozens of consulting rooms, all at the same point. A house without an establishment is not in
DENUE: the search then gives the street.

Run it by hand and commit the files. If a download fails, the old files stay and the script
exits 0. Standard library only.

calles.json (version 1): generated_at, source, boroughs [label], streets [[name, borough,
[lat, lng, lat, lng, …]]]. ``borough`` is an index. The points follow the street, one every
``POINT_SPACING_M`` or more, so the web app finds the point nearest to the person.

numeros.json (version 1): generated_at, source, boroughs [label], neighbourhoods [label],
streets [[name, borough, [[number, lat, lng, neighbourhood], …], blocks]]. ``name`` is the one
in calles.json. ``number`` is text: "49" or "49A". ``neighbourhood`` is an index.

``blocks`` are the segments of the street between two corners, as a straight line:
[[start lat, start lng, end lat, end lng, [[hundred, t0, t1], …]], …]. In a block, the numbers
of one hundred are close together: "Calle Patricio Sanz 500–599" is one block. ``t0`` and ``t1``
are the places, from 0 at the start to 100 at the end, of the number ``hundred * 100`` and of
``hundred * 100 + 99``. The web app uses them for a number that is not in the file and has no
known neighbour at each side.
"""

import argparse
import csv
import io
import json
import math
import re
import sys
import unicodedata
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent.parent / "web" / "public"
OUT = PUBLIC / "calles.json"
OUT_NUMBERS = PUBLIC / "numeros.json"
SOURCE_URL = (
    "https://datos.cdmx.gob.mx/dataset/b9c5307f-0214-4c2c-a4b6-822655303d9c/resource/"
    "d696ef9c-4f3e-49f8-b595-2596dbe5e73a/download/d696ef9c-4f3e-49f8-b595-2596dbe5e73a.json"
)
DENUE_URL = "https://www.inegi.org.mx/contenidos/masiva/denue/denue_09_csv.zip"
DENUE_FILE = "conjunto_de_datos/denue_inegi_09_.csv"
# DENUE is in Windows-1252.
DENUE_ENCODING = "cp1252"
USER_AGENT = "ecobici-dock-availability/0.1 (street index for the web app)"
TIMEOUT_S = 600
# South, west, north, east: the Ecobici stations plus ~1 km. Keep equal to export_places.py.
BOX = (19.334, -99.223, 19.481, -99.121)
# 4 decimals is ~11 m: enough to find the nearest point of a street.
DECIMALS = 4
POINT_SPACING_M = 150
# A number belongs to the segment nearest to its point, if the segment is this close.
BLOCK_MAX_DISTANCE_M = 60
HUNDRED = 100
# INEGI writes "Ninguno" for a street without a name.
NO_NAME = "Ninguno"
BOROUGHS = {
    "002": "Azcapotzalco",
    "003": "Coyoacán",
    "004": "Cuajimalpa de Morelos",
    "005": "Gustavo A. Madero",
    "006": "Iztacalco",
    "007": "Iztapalapa",
    "008": "La Magdalena Contreras",
    "009": "Milpa Alta",
    "010": "Álvaro Obregón",
    "011": "Tláhuac",
    "012": "Tlalpan",
    "013": "Xochimilco",
    "014": "Benito Juárez",
    "015": "Cuauhtémoc",
    "016": "Miguel Hidalgo",
    "017": "Venustiano Carranza",
}
ROAD_WORDS = {
    "calle", "cerrada", "avenida", "privada", "andador", "eje", "calzada", "circuito", "callejon",
    "prolongacion", "carretera", "retorno", "viaducto", "autopista", "boulevard", "continuacion",
    "diagonal", "pasaje", "corredor", "ampliacion", "periferico", "paseo", "anillo", "cuarto",
}  # fmt: skip
# DENUE writes "OTRO(ESPECIFIQUE)" when the type is none of the above.
UNKNOWN_TYPE = "otro"


def label_of(name: str, street_type: str) -> str:
    """ "Calle Durango": the type, unless the name already starts with a road word.
    "Periférico" is a type in INEGI, but the name already says "Boulevard …"."""
    if plain(name).split(" ", 1)[0] in ROAD_WORDS:
        return name
    return f"{street_type} {name}"


def _meters(a: tuple[float, float], b: tuple[float, float]) -> float:
    dlat = (a[0] - b[0]) * 111_320
    dlng = (a[1] - b[1]) * 111_320 * math.cos(math.radians(a[0]))
    return math.hypot(dlat, dlng)


def in_box(lat: float, lng: float) -> bool:
    south, west, north, east = BOX
    return south <= lat <= north and west <= lng <= east


def sampled_points(coordinates: list[list[float]]) -> list[tuple[float, float]]:
    """(lat, lng) of the vertices in the box, at least POINT_SPACING_M apart, with the
    last vertex of the line."""
    kept: list[tuple[float, float]] = []
    for lng, lat in coordinates:
        if not in_box(lat, lng):
            continue
        point = (round(lat, DECIMALS), round(lng, DECIMALS))
        if not kept or _meters(kept[-1], point) >= POINT_SPACING_M:
            kept.append(point)
    return kept


def segment_key(properties: dict) -> tuple[str, int] | None:
    """(street name, borough index) of a segment, or None for a segment without a name."""
    name = (properties["NOMVIAL"] or "").strip()
    codes = list(BOROUGHS)
    if not name or name == NO_NAME or properties["CVE_MUN"] not in codes:
        return None
    return label_of(name, properties["TIPOVIAL"]), codes.index(properties["CVE_MUN"])


def streets(features: list[dict]) -> tuple[list[str], list[list]]:
    """(boroughs, [[name, borough, flat points]]), one street for each name and borough.
    The points of all its segments go together."""
    grouped: dict[tuple[str, int], list[tuple[float, float]]] = {}
    for f in features:
        key = segment_key(f["properties"])
        points = sampled_points(f["geometry"]["coordinates"])
        if key and points:
            grouped.setdefault(key, []).extend(points)
    out = []
    for (name, borough), points in sorted(grouped.items()):
        flat = [v for point in dict.fromkeys(points) for v in point]
        out.append([name, borough, flat])
    return list(BOROUGHS.values()), out


def segment_lines(features: list[dict]) -> dict[tuple[str, int], list[list[tuple[float, float]]]]:
    """The segments of each street, as lines of (lat, lng), when any vertex is in the box."""
    lines: dict[tuple[str, int], list[list[tuple[float, float]]]] = {}
    for f in features:
        key = segment_key(f["properties"])
        line = [(lat, lng) for lng, lat in f["geometry"]["coordinates"]]
        if key and any(in_box(*vertex) for vertex in line):
            lines.setdefault(key, []).append(line)
    return lines


def plain(text: str) -> str:
    """Lowercase, no accents or punctuation: "Niños Héroes" gives "ninos heroes"."""
    folded = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9\s]", " ", folded).split())


def house_number(number: str, letter: str) -> str:
    """ "49" or "49A". DENUE writes "SN" (no number) and words like "BIS" in the letter."""
    number, letter = number.strip(), letter.strip().upper()
    if not number.isdigit():
        return ""
    return number + (letter if re.fullmatch(r"[A-Z]", letter) else "")


def numbers(rows: list[dict], names: dict[tuple[str, str], str]) -> tuple[list[str], list[list]]:
    """(neighbourhoods, [[name, borough, [[number, lat, lng, neighbourhood]]]]): one record
    for each street, number and neighbourhood. ``names`` maps (plain name, borough code) to
    the name of calles.json; a street that is not there keeps the DENUE name."""
    borough_ix = {code: i for i, code in enumerate(BOROUGHS)}
    neighbourhood_ix: dict[str, int] = {}
    grouped: dict[tuple[str, int], dict[tuple[str, int], tuple[float, float]]] = {}
    for row in rows:
        number = house_number(row["numero_ext"], row["letra_ext"])
        street = row["nom_vial"].strip()
        unknown_type = plain(row["tipo_vial"]).startswith(UNKNOWN_TYPE)
        if not number or not street or unknown_type or plain(street) == plain(NO_NAME):
            continue
        if row["cve_mun"] not in borough_ix:
            continue
        try:
            lat, lng = float(row["latitud"]), float(row["longitud"])
        except ValueError:
            continue
        if not in_box(lat, lng):
            continue
        denue_name = label_of(street.title(), row["tipo_vial"].title())
        code = row["cve_mun"]
        name = (
            names.get((plain(denue_name), code)) or names.get((plain(street), code)) or denue_name
        )
        neighbourhood = neighbourhood_ix.setdefault(
            row["nomb_asent"].strip().title(), len(neighbourhood_ix)
        )
        records = grouped.setdefault((name, borough_ix[row["cve_mun"]]), {})
        records.setdefault((number, neighbourhood), (round(lat, 5), round(lng, 5)))
    out = [
        [name, borough, [[n, *point, ix] for (n, ix), point in sorted(records.items())]]
        for (name, borough), records in sorted(grouped.items())
    ]
    return list(neighbourhood_ix), out


def _place_on_line(point: tuple[float, float], line: list[tuple[float, float]]):
    """(distance in m from the point to the line, place of its nearest point as 0–1 of the line)."""
    nearest = (math.inf, 0.0)
    walked = 0.0
    for start, end in zip(line, line[1:], strict=False):
        length = _meters(start, end)
        d_lat, d_lng = end[0] - start[0], end[1] - start[1]
        square = d_lat**2 + d_lng**2
        along = 0.0
        if square:
            along = ((point[0] - start[0]) * d_lat + (point[1] - start[1]) * d_lng) / square
        along = max(0.0, min(1.0, along))
        foot = (start[0] + d_lat * along, start[1] + d_lng * along)
        nearest = min(nearest, (_meters(point, foot), walked + length * along))
        walked += length
    return nearest[0], (nearest[1] / walked if walked else 0.0)


def _hundred_places(anchors: list[tuple[int, float]]) -> tuple[int, int]:
    """Places 0–100 of the first and the last number of the hundred, by least squares. One
    number gives a flat line: its own place."""
    hundred = anchors[0][0] // HUNDRED
    values = [v for v, _ in anchors]
    places = [t for _, t in anchors]
    mean_value, mean_place = sum(values) / len(values), sum(places) / len(places)
    spread = sum((v - mean_value) ** 2 for v in values)
    slope = 0.0
    if spread:
        slope = sum((v - mean_value) * (t - mean_place) for v, t in anchors) / spread

    def at(number: int) -> int:
        return round(max(0.0, min(1.0, mean_place + slope * (number - mean_value))) * 100)

    return at(hundred * HUNDRED), at(hundred * HUNDRED + HUNDRED - 1)


def blocks(records: list[list], lines: list[list[tuple[float, float]]]) -> list[list]:
    """The blocks of a street that have known numbers. See the module docstring."""
    anchors: dict[int, tuple[float, float]] = {}
    for number, lat, lng, _ in records:
        anchors.setdefault(int(re.match(r"\d+", number).group()), (lat, lng))
    by_hundred: dict[tuple[int, int], list[tuple[int, float]]] = {}
    for value, point in anchors.items():
        placed = [(_place_on_line(point, line), i) for i, line in enumerate(lines)]
        (distance, place), segment = min(placed, key=lambda item: item[0][0])
        if distance < BLOCK_MAX_DISTANCE_M:
            by_hundred.setdefault((segment, value // HUNDRED), []).append((value, place))
    out: dict[int, list[list[int]]] = {}
    for (segment, hundred), group in sorted(by_hundred.items()):
        out.setdefault(segment, []).append([hundred, *_hundred_places(group)])
    return [
        [
            round(lines[segment][0][0], 5),
            round(lines[segment][0][1], 5),
            round(lines[segment][-1][0], 5),
            round(lines[segment][-1][1], 5),
            hundreds,
        ]
        for segment, hundreds in out.items()
    ]


def with_blocks(
    found: list[list], lines: dict[tuple[str, int], list[list[tuple[float, float]]]]
) -> list[list]:
    """The streets of ``numbers`` with their blocks as a fourth item. A street that is not in
    the segment file has no blocks."""
    return [
        [
            name,
            borough,
            records,
            blocks(records, lines[(name, borough)]) if (name, borough) in lines else [],
        ]
        for name, borough, records in found
    ]


def fetch_denue() -> list[dict]:
    req = urllib.request.Request(DENUE_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as res:
        archive = zipfile.ZipFile(io.BytesIO(res.read()))
    with archive.open(DENUE_FILE) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding=DENUE_ENCODING, errors="replace")))


def fetch() -> list[dict]:
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as res:
        return json.load(res)["features"]


def street_names(found: list[list]) -> dict[tuple[str, str], str]:
    """(plain name, borough code) to the name of calles.json. A name with no type also
    works ("durango"), for a DENUE street with another type than INEGI."""
    codes = list(BOROUGHS)
    full = {(plain(name), codes[borough]): name for name, borough, _ in found}
    untyped: dict[tuple[str, str], str] = {}
    for name, borough, _ in found:
        first, _, rest = plain(name).partition(" ")
        if first in ROAD_WORDS and rest:
            untyped.setdefault((rest, codes[borough]), name)
    return untyped | full


def write(path: Path, data: dict, summary: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{path}: {summary}, {path.stat().st_size // 1024} KB")


def header(source: str) -> dict:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    return {"version": 1, "generated_at": generated_at, "source": source}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--out-numbers", type=Path, default=OUT_NUMBERS)
    a = ap.parse_args(argv)
    try:
        features = fetch()
        boroughs, found = streets(features)
        neighbourhoods, with_numbers = numbers(fetch_denue(), street_names(found))
        with_numbers = with_blocks(with_numbers, segment_lines(features))
    except (OSError, ValueError, KeyError) as e:
        print(f"Download failed ({e}); the old files stay.", file=sys.stderr)
        return 0
    source = "INEGI, Vialidades de la Ciudad de México (CC-BY-4.0-ESP)"
    write(a.out, header(source) | {"boroughs": boroughs, "streets": found}, f"{len(found)} streets")
    source = "INEGI, DENUE Ciudad de México; vialidades: INEGI (CC-BY-4.0-ESP)"
    data = header(source) | {
        "boroughs": boroughs,
        "neighbourhoods": neighbourhoods,
        "streets": with_numbers,
    }
    write(a.out_numbers, data, f"{sum(len(r[2]) for r in with_numbers)} addresses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
