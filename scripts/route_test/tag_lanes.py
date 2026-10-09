"""Copy an OSM file and mark each bike-lane way, so GraphHopper can route by lane class.

    uv run --with osmium python scripts/route_test/tag_lanes.py IN.osm.pbf OUT.osm.pbf

GraphHopper has no encoded value for painted lanes, and its ``bike_priority`` rates a
residential street with no lane above a street with a painted lane. So each lane way gets
a synthetic ``route=mtb`` relation, and ``mtb_network`` carries the class:
icn = separated, ncn = painted, rcn = shared. No bike profile reads ``mtb_network``.
"""

import sys

import osmium

from ecobici.bike_lanes import PAINTED, SEPARATED, SHARED, lane_class

NETWORK = {SEPARATED: "icn", PAINTED: "ncn", SHARED: "rcn"}
# Above every real OSM relation id.
FIRST_RELATION_ID = 9_000_000_000


class CopyAndClassify(osmium.SimpleHandler):
    def __init__(self, writer: osmium.SimpleWriter):
        super().__init__()
        self.writer = writer
        self.lanes: dict[int, str] = {}

    def node(self, n):
        self.writer.add_node(n)

    def way(self, w):
        self.writer.add_way(w)
        cls = lane_class({t.k: t.v for t in w.tags})
        if cls:
            self.lanes[w.id] = cls

    def relation(self, r):
        self.writer.add_relation(r)


def main(src: str, dst: str) -> int:
    writer = osmium.SimpleWriter(dst, overwrite=True)
    copy = CopyAndClassify(writer)
    copy.apply_file(src)
    for i, (way_id, cls) in enumerate(sorted(copy.lanes.items())):
        writer.add_relation(
            osmium.osm.mutable.Relation(
                id=FIRST_RELATION_ID + i,
                version=1,
                members=[("w", way_id, "")],
                tags={"type": "route", "route": "mtb", "network": NETWORK[cls]},
            )
        )
    writer.close()
    counts = {c: sum(v == c for v in copy.lanes.values()) for c in NETWORK}
    print(f"{dst}: {len(copy.lanes)} lane ways {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
