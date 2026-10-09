"""Bike-lane class of an OpenStreetMap way, from its tags.

- ``separated``: a cycleway or a track that cars cannot use.
- ``painted``: a lane painted on the street.
- ``shared``: a lane shared with buses or a pictogram on the street (sharrow).

The route test (docs/reports/ciclovias_graphhopper.md) and the map layer use these rules.
"""

SEPARATED = "separated"
PAINTED = "painted"
SHARED = "shared"
LANE_CLASSES = (SEPARATED, PAINTED, SHARED)

SIDE_KEYS = ("cycleway", "cycleway:left", "cycleway:right", "cycleway:both")
# "separate" is not here: the lane is its own way, and the street itself has no lane.
SEPARATED_VALUES = {"track", "opposite_track"}
PAINTED_VALUES = {"lane", "opposite_lane"}
SHARED_VALUES = {"shared_lane", "share_busway", "opposite_share_busway"}


def lane_class(tags: dict[str, str]) -> str | None:
    """The lane class of a way, or None. With different sides, the better side wins."""
    highway = tags.get("highway")
    if highway == "cycleway" or (highway == "path" and tags.get("bicycle") == "designated"):
        return SEPARATED
    sides = {tags.get(k) for k in SIDE_KEYS}
    if sides & SEPARATED_VALUES:
        return SEPARATED
    if sides & PAINTED_VALUES:
        return PAINTED
    if sides & SHARED_VALUES:
        return SHARED
    return None
