import gzip
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import polars as pl
import pytest
from fastapi.testclient import TestClient

from ecobici.api import make_app
from ecobici.collector.sinks import LocalSink
from ecobici.feedback import RateLimit
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
def client(tmp_path):
    return TestClient(make_app(FakeService(), plan_sink=LocalSink(tmp_path / "plans")))


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


def test_no_captures_is_503_and_health_still_answers(tmp_path):
    client = TestClient(make_app(FakeService(captures=False), plan_sink=LocalSink(tmp_path)))
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


@pytest.fixture
def sink(tmp_path):
    return LocalSink(tmp_path)


@pytest.fixture
def fb_client(sink):
    return TestClient(make_app(FakeService(), feedback_sink=sink))


def answer(**over):
    return {
        "kind": "trip",
        "plan_id": str(uuid4()),
        "captured_at": datetime.now(UTC).isoformat(),
        "pickup_id": "O",
        "dropoff_id": "B",
        "rank": 1,
        "p_free": 0.9,
        "found_dock": "yes",
        "found_bike": "yes",
    } | over


def saved(sink) -> list[dict]:
    return [json.loads(gzip.decompress(p.read_bytes())) for p in sink.root.rglob("*.json.gz")]


def test_a_trip_answer_is_saved_without_the_client_address(fb_client, sink):
    assert fb_client.post("/v1/feedback", json=answer()).status_code == 204
    [record] = saved(sink)
    assert record["found_dock"] == "yes" and record["dropoff_id"] == "B"
    assert "received_at" in record
    assert "testclient" not in json.dumps(record)


def test_a_second_answer_to_the_same_question_replaces_the_first(fb_client, sink):
    first = answer(found_dock="yes")
    fb_client.post("/v1/feedback", json=first)
    fb_client.post("/v1/feedback", json=first | {"found_dock": "no"})
    rating = answer(
        kind="rating", plan_id=first["plan_id"], useful=False, reason="far", comment="Lejos"
    )
    assert fb_client.post("/v1/feedback", json=rating).status_code == 204
    by_kind = {r["kind"]: r for r in saved(sink)}
    assert by_kind["trip"]["found_dock"] == "no"
    assert by_kind["rating"]["reason"] == "far"


@pytest.mark.parametrize(
    "bad",
    [
        {"dropoff_id": "nope"},
        {"captured_at": (datetime.now(UTC) - timedelta(days=3)).isoformat()},
        {"captured_at": "2026-10-07T12:00:00"},
        {"p_free": 1.5},
        {"found_dock": "maybe"},
        {"kind": "rating", "useful": True, "comment": "x" * 281},
        {"plan_id": "not-a-uuid"},
    ],
)
def test_invalid_answers_are_rejected(fb_client, sink, bad):
    assert fb_client.post("/v1/feedback", json=answer(**bad)).status_code == 422
    assert saved(sink) == []


def test_too_many_answers_from_one_client_are_refused(fb_client):
    codes = [fb_client.post("/v1/feedback", json=answer()).status_code for _ in range(31)]
    assert codes[:30] == [204] * 30 and codes[30] == 429


def test_rate_limit_forgets_old_calls(monkeypatch):
    clock = iter([0.0, 1.0, 2.0, 100.0])
    monkeypatch.setattr("ecobici.feedback.time.monotonic", lambda: next(clock))
    limit = RateLimit(2, 50)
    assert [limit.allow("a") for _ in range(3)] == [True, True, False]
    assert limit.allow("a")
    assert list(limit.calls) == ["a"]


def test_cors_allows_the_feedback_post(fb_client):
    r = fb_client.options(
        "/v1/feedback",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200


@pytest.fixture
def plan_sink(tmp_path):
    return LocalSink(tmp_path / "plans")


@pytest.fixture
def plan_client(plan_sink):
    return TestClient(make_app(FakeService(), plan_sink=plan_sink))


def plan_query(**over):
    return {
        "from_station": "O",
        "to_lat": 19.4,
        "to_lng": -99.17,
        "plan_id": str(uuid4()),
        "from_kind": "station",
        "to_kind": "photon",
        "to_name": "Torre Reforma",
        "to_osm": "W123",
    } | over


def test_a_plan_is_saved_once_with_the_public_destination(plan_client, plan_sink):
    q = plan_query()
    assert plan_client.get("/v1/plan", params=q).status_code == 200
    assert plan_client.get("/v1/plan", params=q).status_code == 200
    [record] = saved(plan_sink)
    assert plan_sink.root.joinpath("2026/10/07", f"{q['plan_id']}.json.gz").exists()
    assert record["plan_id"] == q["plan_id"] and record["pickup_id"] == "O"
    assert record["from"] == {"kind": "station", "name": None, "osm": None, "station_id": "O"}
    assert record["to"] == {
        "kind": "photon",
        "name": "Torre Reforma",
        "osm": "W123",
        "lat": 19.4,
        "lng": -99.17,
    }
    cands = {c["id"]: c for c in record["candidates"]}
    assert set(cands) == {"A", "B", "F"}
    assert cands["B"]["p_free"] is not None and cands["B"]["walk_m"] > 0
    # F is the nearest to the destination, then A, then B.
    assert [cands[i]["walk_order"] for i in "FAB"] == [1, 2, 3]


def test_a_private_end_keeps_no_point_and_no_distances(plan_client, plan_sink):
    q = plan_query(
        from_lat=19.3801,
        from_lng=-99.17,
        from_kind="location",
        to_kind="address",
        to_name="Calle Falsa 123",
    )
    del q["from_station"]
    assert plan_client.get("/v1/plan", params=q).status_code == 200
    [record] = saved(plan_sink)
    assert record["from"] == {"kind": "location"} and record["to"] == {"kind": "address"}
    text = json.dumps(record)
    assert "19.38" not in text and "Falsa" not in text
    for row in record["pickups"] + record["candidates"]:
        assert "walk_m" not in row and "walk_min" not in row and row["walk_order"] >= 1
        assert "total_min" not in row and "expected_min" not in row
    assert {c["walk_order"] for c in record["candidates"]} == {1, 2, 3}


def test_a_plan_without_an_id_is_not_saved(plan_client, plan_sink):
    q = plan_query()
    del q["plan_id"]
    assert plan_client.get("/v1/plan", params=q).status_code == 200
    assert saved(plan_sink) == []


@pytest.mark.parametrize(
    "bad", [{"plan_id": "nope"}, {"to_kind": "home"}, {"to_osm": "X1"}, {"to_name": "x" * 121}]
)
def test_invalid_plan_fields_are_rejected(plan_client, plan_sink, bad):
    assert plan_client.get("/v1/plan", params=plan_query(**bad)).status_code == 422
    assert saved(plan_sink) == []


def test_a_failed_save_still_answers_the_plan(plan_sink):
    class Broken:
        def put(self, key, body):
            raise OSError("disk full")

    client = TestClient(make_app(FakeService(), plan_sink=Broken()))
    assert client.get("/v1/plan", params=plan_query()).status_code == 200


def test_too_many_plans_from_one_client_are_answered_but_not_saved(plan_client, plan_sink):
    codes = [plan_client.get("/v1/plan", params=plan_query()).status_code for _ in range(121)]
    assert codes == [200] * 121
    assert len(saved(plan_sink)) == 120


def test_without_a_plan_sink_the_plan_is_answered_and_not_saved(monkeypatch, tmp_path):
    monkeypatch.delenv("ECOBICI_PLAN_SINK", raising=False)
    monkeypatch.chdir(tmp_path)
    client = TestClient(make_app(FakeService(), feedback_sink=LocalSink(tmp_path / "fb")))
    assert client.get("/v1/plan", params=plan_query()).status_code == 200
    assert list(tmp_path.rglob("*.json.gz")) == []
