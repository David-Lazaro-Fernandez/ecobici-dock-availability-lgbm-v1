import pytest

from ecobici.bike_lanes import PAINTED, SEPARATED, SHARED, lane_class


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({"highway": "cycleway"}, SEPARATED),
        ({"highway": "path", "bicycle": "designated"}, SEPARATED),
        ({"highway": "secondary", "cycleway:right": "track"}, SEPARATED),
        ({"highway": "residential", "cycleway": "opposite_track"}, SEPARATED),
        ({"highway": "tertiary", "cycleway:both": "lane"}, PAINTED),
        ({"highway": "residential", "cycleway:left": "opposite_lane"}, PAINTED),
        ({"highway": "primary", "cycleway:right": "share_busway"}, SHARED),
        ({"highway": "residential", "cycleway:right": "shared_lane"}, SHARED),
    ],
)
def test_lane_class(tags, expected):
    assert lane_class(tags) == expected


def test_better_side_wins():
    tags = {"highway": "secondary", "cycleway:left": "shared_lane", "cycleway:right": "track"}
    assert lane_class(tags) == SEPARATED


@pytest.mark.parametrize(
    "tags",
    [
        {"highway": "residential"},
        {"highway": "path"},
        {"highway": "primary", "cycleway": "no"},
        {"highway": "primary", "cycleway:right": "separate"},
    ],
)
def test_no_lane(tags):
    assert lane_class(tags) is None
