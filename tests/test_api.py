from datetime import UTC, datetime

import polars as pl
import pytest
from fastapi.testclient import TestClient

from ecobici.api import make_app
from ecobici.serve import Live, LiveService

T0 = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)


class FakeService(LiveService):
    """Synthetic stations on a north–south line; no model, no S3."""

    def __init__(self, captures: bool = True):
        super().__init__(use_s3=False)
        self.captures = captures
        self.stations = pl.DataFrame(
            {
                "station_id": ["O", "A", "B", "F"],
                "short_name": ["001", "002", "003", "004"],
                "name": ["Origin", "Near", "Farther", "Broken"],
                "lat": [19.380, 19.4010, 19.4025, 19.4005],
                "lon": [-99.170] * 4,
                "capacity": [20, 20, 20, 20],
                "num_docks_available": [5, 0, 7, 3],
                "num_bikes_available": [12, 20, 13, 0],
                "label": ["available", "full", "available", "unavailable"],
                "p_full_15": [0.0, 0.9, 0.1, None],
                "p_full_30": [0.0, 0.8, 0.2, None],
                "p_full_45": [0.0, 0.7, 0.3, None],
            }
        )

    def current(self) -> Live:
        if not self.captures:
            raise LookupError("no captures yet")
        return Live(T0, self.stations, weather_missing=False)

    def rides(self) -> pl.DataFrame:
        return pl.DataFrame(
            {"origin_id": ["O"], "destination_id": ["B"], "ride_min": [20.0], "trips": [40]}
        )


@pytest.fixture
def client():
    return TestClient(make_app(FakeService()))


def test_stations_lists_predictions_keyed_by_horizon(client):
    body = client.get("/v1/stations").json()
    assert body["horizons"] == [15, 30, 45]
    by = {s["id"]: s for s in body["stations"]}
    assert by["A"]["p_full"] == {"15": 0.9, "30": 0.8, "45": 0.7}
    assert by["F"]["p_full"] is None and by["F"]["state"] == "unavailable"
    assert by["A"]["lng"] == -99.17 and by["A"]["code"] == "002"


def test_plan_from_a_point_picks_the_nearest_bike_and_ranks_candidates(client):
    r = client.get(
        "/v1/plan",
        params={"from_lat": 19.3801, "from_lng": -99.17, "to_lat": 19.4, "to_lng": -99.17},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["pickup"]["id"] == "O" and body["pickup"]["walk_m"] > 0
    cands = {c["id"]: c for c in body["candidates"]}
    assert set(cands) == {"A", "B", "F"}
    assert cands["B"]["ride_source"] == "median of 40 trips"
    # Arrival = walk to the pickup + a 20-min ride, between the 15 (0.1) and 30 (0.2) min
    # models: P(full) ≈ 0.133 plus the walk's share.
    walk = body["pickup"]["walk_min"]
    assert cands["B"]["p_free"] == pytest.approx(1 - (0.1 + (5 + walk) / 15 * 0.1))
    assert cands["F"]["rank"] is None and not cands["F"]["recommendable"]
    assert [c["rank"] for c in body["candidates"] if c["rank"]] == [1, 2]
    # Arrival = capture + walk to the pickup + ride.
    arrive = datetime.fromisoformat(cands["B"]["arrive_at"])
    walk = body["pickup"]["walk_min"]
    assert (arrive - T0).total_seconds() / 60 == pytest.approx(walk + 20, abs=0.01)


def test_plan_from_a_station(client):
    r = client.get("/v1/plan", params={"from_station": "O", "to_lat": 19.4, "to_lng": -99.17})
    assert r.status_code == 200 and r.json()["pickup"]["walk_m"] == 0


def test_plan_validates_input(client):
    assert client.get("/v1/plan", params={"to_lat": 19.4, "to_lng": -99.17}).status_code == 422
    bad = {"from_station": "nope", "to_lat": 19.4, "to_lng": -99.17}
    assert client.get("/v1/plan", params=bad).status_code == 422
    too_far = {"from_station": "O", "to_lat": 19.4, "to_lng": -99.17, "radius_m": 5000}
    assert client.get("/v1/plan", params=too_far).status_code == 422


def test_no_captures_is_503_and_health_still_answers():
    client = TestClient(make_app(FakeService(captures=False)))
    assert client.get("/v1/stations").status_code == 503
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["captured_at"] is None


def test_cors_allows_the_next_dev_server(client):
    r = client.get("/v1/stations", headers={"Origin": "http://localhost:3000"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_an_empty_start_station_moves_the_pickup_to_the_nearest_bike():
    svc = FakeService()
    # "O" has no bike now; "A" (full, 20 bikes) is the nearest with one.
    svc.stations = svc.stations.with_columns(
        num_bikes_available=pl.when(pl.col("station_id") == "O")
        .then(0)
        .otherwise(pl.col("num_bikes_available"))
    )
    body = (
        TestClient(make_app(svc))
        .get("/v1/plan", params={"from_station": "O", "to_lat": 19.4, "to_lng": -99.17})
        .json()
    )
    assert body["requested"]["id"] == "O" and body["requested"]["bikes"] == 0
    # A is full (no free dock) but has bikes to lend, and it is the nearest such station.
    assert body["pickup"]["id"] == "A"
    assert body["pickup"]["walk_m"] > 0


def test_a_start_station_with_bikes_is_the_pickup():
    body = (
        TestClient(make_app(FakeService()))
        .get("/v1/plan", params={"from_station": "O", "to_lat": 19.4, "to_lng": -99.17})
        .json()
    )
    assert body["requested"] is None and body["pickup"]["id"] == "O"


def test_the_pickup_weighs_the_chance_of_finding_no_bike():
    svc = FakeService()
    # N is a second station 160 m north of O. From a point next to O, O is nearer but
    # likely empty by the time you get there; N is safe.
    near = svc.stations.filter(pl.col("station_id") == "O").with_columns(
        station_id=pl.lit("N"),
        short_name=pl.lit("005"),
        name=pl.lit("Next door"),
        lat=pl.lit(19.3815),
    )
    svc.stations = pl.concat([svc.stations, near]).with_columns(
        p_empty_15=pl.when(pl.col("station_id") == "O").then(0.95).otherwise(0.0)
    )
    body = (
        TestClient(make_app(svc))
        .get(
            "/v1/plan",
            params={
                "from_lat": 19.3803,
                "from_lng": -99.17,
                "to_lat": 19.4,
                "to_lng": -99.17,
                "failure_min": 30,
            },
        )
        .json()
    )
    opts = {o["id"]: o for o in body["pickup_options"]}
    assert set(opts) == {"O", "N"}
    assert opts["O"]["walk_m"] < opts["N"]["walk_m"]
    assert opts["O"]["p_empty_at_arrival"] > 0 and opts["N"]["p_empty_at_arrival"] == 0
    assert body["pickup"]["id"] == "N"
    assert body["pickup_options"][0]["id"] == "N"
