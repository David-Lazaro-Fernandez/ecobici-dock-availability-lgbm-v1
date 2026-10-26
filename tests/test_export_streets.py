import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "export_streets.py"
spec = importlib.util.spec_from_file_location("export_streets", SCRIPT)
export_streets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_streets)


def feature(name, street_type, mun, coordinates):
    return {
        "properties": {"NOMVIAL": name, "TIPOVIAL": street_type, "CVE_MUN": mun},
        "geometry": {"type": "LineString", "coordinates": coordinates},
    }


@pytest.mark.parametrize(
    ("name", "street_type", "expected"),
    [
        ("Durango", "Calle", "Calle Durango"),
        ("Insurgentes Sur", "Avenida", "Avenida Insurgentes Sur"),
        ("Boulevard Adolfo López Mateos", "Periférico", "Boulevard Adolfo López Mateos"),
        ("Eje 3 Norte", "Eje Vial", "Eje 3 Norte"),
    ],
)
def test_label_of(name, street_type, expected):
    assert export_streets.label_of(name, street_type) == expected


def test_segments_of_one_street_and_borough_go_together():
    features = [
        feature("Durango", "Calle", "015", [[-99.1625, 19.4206], [-99.1620, 19.4207]]),
        feature("Durango", "Calle", "015", [[-99.1575, 19.4222]]),
        feature("Durango", "Calle", "002", [[-99.1908, 19.4767]]),
    ]
    boroughs, found = export_streets.streets(features)
    assert [(name, boroughs[b]) for name, b, _ in found] == [
        ("Calle Durango", "Azcapotzalco"),
        ("Calle Durango", "Cuauhtémoc"),
    ]
    assert found[1][2] == [19.4206, -99.1625, 19.4222, -99.1575]


def test_streets_without_a_name_or_outside_the_box_are_dropped():
    features = [
        feature("Ninguno", "Calle", "015", [[-99.16, 19.42]]),
        feature("Lejos", "Calle", "015", [[-99.5, 19.9]]),
        feature("Fuera", "Calle", "099", [[-99.16, 19.42]]),
    ]
    assert export_streets.streets(features)[1] == []


def test_points_keep_a_minimum_spacing():
    line = [[-99.16 + i * 0.0001, 19.42] for i in range(300)]
    points = export_streets.sampled_points(line)
    assert 1 < len(points) < 40


def denue(
    street,
    number,
    mun="015",
    letter="",
    street_type="CALLE",
    neighbourhood="ROMA NORTE",
    lat="19.42192",
    lng="-99.15708",
):
    return {
        "nom_vial": street,
        "tipo_vial": street_type,
        "numero_ext": number,
        "letra_ext": letter,
        "cve_mun": mun,
        "nomb_asent": neighbourhood,
        "latitud": lat,
        "longitud": lng,
    }


def test_house_number():
    assert export_streets.house_number("49", "") == "49"
    assert export_streets.house_number("49", "a") == "49A"
    assert export_streets.house_number("49", "BIS") == "49"
    assert export_streets.house_number("", "SN") == ""
    assert export_streets.house_number("KM 5", "") == ""


def test_plain():
    assert export_streets.plain("Niños Héroes, 5 de Mayo") == "ninos heroes 5 de mayo"


def test_an_address_has_one_point_and_the_street_name_of_calles_json():
    rows = [denue("DURANGO", "49"), denue("DURANGO", "49"), denue("DURANGO", "49", letter="A")]
    names = {("calle durango", "015"): "Calle Durango"}
    neighbourhoods, found = export_streets.numbers(rows, names)
    assert neighbourhoods == ["Roma Norte"]
    assert found == [
        ["Calle Durango", 13, [["49", 19.42192, -99.15708, 0], ["49A", 19.42192, -99.15708, 0]]]
    ]


def test_an_unknown_street_keeps_the_denue_name_and_a_street_with_another_type_is_found():
    rows = [denue("LUISIANA", "12"), denue("DURANGO", "7", street_type="AVENIDA")]
    names = {("durango", "015"): "Calle Durango"}
    _, found = export_streets.numbers(rows, names)
    assert sorted(name for name, _, _ in found) == ["Calle Durango", "Calle Luisiana"]


def test_rows_without_a_street_number_or_place_are_dropped():
    rows = [
        denue("NINGUNO", "5"),
        denue("DURANGO", ""),
        denue("DURANGO", "5", street_type="OTRO(ESPECIFIQUE)"),
        denue("DURANGO", "5", lat="19.9", lng="-99.5"),
        denue("DURANGO", "5", lat="", lng=""),
        denue("DURANGO", "5", mun="099"),
    ]
    assert export_streets.numbers(rows, {})[1] == []


def test_street_names_find_a_name_without_its_type():
    names = export_streets.street_names([["Calle Durango", 13, []]])
    assert names[("durango", "015")] == "Calle Durango"
    assert names[("calle durango", "015")] == "Calle Durango"


# Two segments of one street, each about 111 m long, one after the other.
FIRST_SEGMENT = [(19.4000, -99.1500), (19.4010, -99.1500)]
SECOND_SEGMENT = [(19.4010, -99.1500), (19.4020, -99.1500)]


def record(number, lat):
    return [number, lat, -99.1500, 0]


def test_a_block_has_the_places_of_the_first_and_the_last_number_of_its_hundred():
    records = [record("501", 19.40011), record("509", 19.40099)]
    found = export_streets.blocks(records, [FIRST_SEGMENT, SECOND_SEGMENT])
    assert found == [[19.4, -99.15, 19.401, -99.15, [[5, 0, 100]]]]


def test_one_number_gives_a_flat_line_and_each_segment_its_own_hundreds():
    records = [record("305", 19.4015), record("612", 19.4005), record("640", 19.4008)]
    found = export_streets.blocks(records, [FIRST_SEGMENT, SECOND_SEGMENT])
    assert found == [
        [19.4, -99.15, 19.401, -99.15, [[6, 37, 100]]],
        [19.401, -99.15, 19.402, -99.15, [[3, 50, 50]]],
    ]


def test_a_number_far_from_the_street_gives_no_block():
    assert export_streets.blocks([["50", 19.41, -99.15, 0]], [FIRST_SEGMENT]) == []


def test_numbers_with_a_letter_count_by_their_digits():
    found = export_streets.blocks([record("510B", 19.4005)], [FIRST_SEGMENT])
    assert found[0][4] == [[5, 50, 50]]


def test_a_street_that_is_not_in_the_segments_has_no_blocks():
    found = [["Calle Luisiana", 13, [record("12", 19.4005)]]]
    assert export_streets.with_blocks(found, {}) == [["Calle Luisiana", 13, found[0][2], []]]


def test_segment_lines_group_by_street_name_and_borough():
    def feature(name, mun, coordinates):
        properties = {"NOMVIAL": name, "TIPOVIAL": "Calle", "CVE_MUN": mun}
        return {"properties": properties, "geometry": {"coordinates": coordinates}}

    lines = export_streets.segment_lines(
        [
            feature("Durango", "015", [[-99.15, 19.4], [-99.15, 19.401]]),
            feature("Durango", "015", [[-99.15, 19.401], [-99.15, 19.402]]),
            feature("Lejos", "015", [[-99.5, 19.9]]),
            feature("Ninguno", "015", [[-99.15, 19.4]]),
        ]
    )
    assert list(lines) == [("Calle Durango", 13)]
    assert lines[("Calle Durango", 13)][0] == [(19.4, -99.15), (19.401, -99.15)]
