"""The HTTP API for the web app (``web/``): live station predictions and trip plans.

    uv run --extra api --extra model uvicorn ecobici.api:app --port 8000

Interactive docs: http://localhost:8000/docs. GET, plus POST /v1/feedback (anonymous,
see ``ecobici.feedback``). Each plan with a ``plan_id`` is saved, see ``ecobici.plans``.
CORS allows the origins in ECOBICI_API_ORIGINS (comma-separated; default: the Next dev
server). The logic is in ``ecobici.serve.LiveService``. This module only reads requests
and writes responses.
"""

import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import AwareDatetime, BaseModel, Field

from ecobici import feedback as fb
from ecobici import plans
from ecobici.collector.sinks import Sink
from ecobici.eval.baseline_report import HORIZONS
from ecobici.serve import LiveService

ORIGINS = os.environ.get("ECOBICI_API_ORIGINS", "http://localhost:3000").split(",")
MAX_RADIUS_M = 1500
MAX_FAILURE_MIN = 30
FEEDBACK_PER_HOUR = 30
# More plans from one client are answered but not saved.
PLANS_SAVED_PER_HOUR = 120
MAX_PLACE_NAME = 120
MAX_OSM_ID = 24
# The trip question comes back for some hours after the arrival.
FEEDBACK_MAX_AGE = timedelta(days=2)
MAX_COMMENT = 280


class Station(BaseModel):
    id: str
    code: str
    name: str
    lat: float
    lng: float
    capacity: int | None
    docks: int | None
    bikes: int | None
    # Available | full | unavailable | stale.
    state: str
    # P(full) at 15, 30 and 45 min, keyed by minutes. Null if not predicted.
    p_full: dict[str, float] | None
    # P(no bike) at 15 min, keyed by minutes. Null without the empty-station model.
    p_empty: dict[str, float] | None = None


class StationsResponse(BaseModel):
    captured_at: datetime
    weather_missing: bool
    horizons: list[int]
    stations: list[Station]


class Pickup(Station):
    walk_m: float
    walk_min: float
    # P(no bike left on arrival). 0 at the start station.
    p_empty_at_arrival: float | None
    # Walk + P(no bike) × failure cost + expected minutes of the best drop-off.
    total_min: float | None


class Candidate(Station):
    # 1 = best. Null if not recommendable (out of service or stale).
    rank: int | None
    recommendable: bool
    # To the destination.
    walk_m: float
    walk_min: float
    ride_min: float
    ride_source: str
    arrive_at: datetime
    p_full_at_arrival: float | None
    p_free: float | None
    # From the pickup: ride + walk + P(full) × failure cost.
    expected_min: float | None
    outside_horizons: bool


class PlanResponse(BaseModel):
    captured_at: datetime
    weather_missing: bool
    radius_m: float
    failure_min: float
    pickup: Pickup
    # The compared pickups, lowest total first. The first one is `pickup`.
    pickup_options: list[Pickup]
    # The start station asked for, if it had no bike to take. Then `pickup` is a station
    # nearby.
    requested: Station | None
    candidates: list[Candidate]


Probability = Annotated[float, Field(ge=0, le=1)]


class Shown(BaseModel):
    """The plan the person saw. The web app makes ``plan_id`` once per plan."""

    plan_id: UUID
    captured_at: AwareDatetime
    pickup_id: str
    dropoff_id: str
    rank: int | None = None
    arrive_at: AwareDatetime | None = None
    p_free: Probability | None = None
    p_empty_at_arrival: Probability | None = None


class Rating(Shown):
    kind: Literal["rating"]
    useful: bool
    reason: Literal["far", "wrong_time", "wrong_data", "other"] | None = None
    comment: Annotated[str, Field(max_length=MAX_COMMENT)] | None = None


class TripResult(Shown):
    kind: Literal["trip"]
    found_dock: Literal["yes", "no", "no_trip"]
    found_bike: Literal["yes", "no"] | None = None


Feedback = Annotated[Rating | TripResult, Field(discriminator="kind")]


class Health(BaseModel):
    status: str
    captured_at: datetime | None
    s3_error: str | None


def finite(v: float | None) -> float | None:
    return None if v is None or v != v or v in (float("inf"), float("-inf")) else v


def pickup(row: dict) -> dict:
    return {
        **station(row),
        "walk_m": row["walk_m"],
        "walk_min": row["walk_min"],
        "p_empty_at_arrival": finite(row.get("p_empty")),
        "total_min": finite(row.get("total_min")),
    }


def station(row: dict) -> dict:
    p = {str(h): row[f"p_full_{h}"] for h in HORIZONS if row.get(f"p_full_{h}") is not None}
    empty = {
        k.removeprefix("p_empty_"): v
        for k, v in row.items()
        if k.startswith("p_empty_") and v is not None
    }
    return {
        "id": row["station_id"],
        "code": row["short_name"],
        "name": row["name"],
        "lat": row["lat"],
        "lng": row["lon"],
        "capacity": row.get("capacity"),
        "docks": row.get("num_docks_available"),
        "bikes": row.get("num_bikes_available"),
        "state": row["label"],
        "p_full": p or None,
        "p_empty": empty or None,
    }


PlaceName = Annotated[str | None, Query(max_length=MAX_PLACE_NAME)]
OsmId = Annotated[str | None, Query(pattern=r"^[NWR]\d+$", max_length=MAX_OSM_ID)]

log = logging.getLogger(__name__)


def plan_record(
    response: PlanResponse, plan_id: UUID, ends: dict[str, dict], from_station: str | None
) -> dict:
    """The plan to save: the ends of the trip, the ids and the predictions sent."""
    from_public = ends["from"]["kind"] in plans.PUBLIC_KINDS
    to_public = ends["to"]["kind"] in plans.PUBLIC_KINDS
    pickup_fields = ("id", "walk_m", "walk_min", "p_empty_at_arrival", "total_min")
    candidate_fields = (
        "id",
        "rank",
        "recommendable",
        "walk_m",
        "walk_min",
        "ride_min",
        "ride_source",
        "arrive_at",
        "p_full_at_arrival",
        "p_free",
        "expected_min",
        "outside_horizons",
    )
    body = response.model_dump(mode="json")
    pickups = [{k: o[k] for k in pickup_fields} for o in body["pickup_options"]]
    candidates = [{k: c[k] for k in candidate_fields} for c in body["candidates"]]
    return {
        "plan_id": str(plan_id),
        "captured_at": response.captured_at.isoformat(),
        "weather_missing": response.weather_missing,
        "radius_m": response.radius_m,
        "failure_min": response.failure_min,
        "from": ends["from"] | ({"station_id": from_station} if from_station else {}),
        "to": ends["to"],
        "pickup_id": response.pickup.id,
        "requested_id": response.requested.id if response.requested else None,
        "pickups": plans.by_walk_order(pickups, from_public),
        "candidates": plans.by_walk_order(candidates, to_public),
    }


def make_app(
    service: LiveService | None = None,
    feedback_sink: Sink | None = None,
    plan_sink: Sink | None = None,
) -> FastAPI:
    svc = service or LiveService()
    sink = feedback_sink or fb.default_sink()
    plan_store = plan_sink or plans.default_sink()
    if plan_store is None:
        log.warning("%s is not set: plans are not saved", plans.SINK_ENV)
    limit = fb.RateLimit(FEEDBACK_PER_HOUR, 3600)
    plan_limit = fb.RateLimit(PLANS_SAVED_PER_HOUR, 3600)
    saved_plans = plans.Seen()

    def save_plan(record: dict, captured_at: datetime) -> None:
        try:
            plans.write(plan_store, record, captured_at)
        # The plan is already sent. A failed save must not stop the API.
        except Exception:  # noqa: BLE001
            log.exception("could not save plan %s", record["plan_id"])

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Load the model (~20 s) in the background, so /health answers at once.
        if service is None:
            threading.Thread(target=svc.current, daemon=True).start()
        yield

    app = FastAPI(title="Ecobici dock availability", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"]
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    def live_or_503():
        try:
            return svc.current()
        except LookupError as e:
            raise HTTPException(503, str(e)) from e

    @app.get("/health")
    def health() -> Health:
        return Health(status="ok", captured_at=svc.last_capture, s3_error=svc.s3_error)

    @app.get("/v1/stations")
    def stations() -> StationsResponse:
        now = live_or_503()
        return StationsResponse(
            captured_at=now.captured_at,
            weather_missing=now.weather_missing,
            horizons=list(HORIZONS),
            stations=[station(r) for r in now.stations.drop_nulls(["lat", "lon"]).to_dicts()],
        )

    @app.get("/v1/plan")
    def plan(
        request: Request,
        background: BackgroundTasks,
        to_lat: Annotated[float, Query(ge=-90, le=90)],
        to_lng: Annotated[float, Query(ge=-180, le=180)],
        from_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
        from_lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
        from_station: str | None = None,
        radius_m: Annotated[float, Query(gt=0, le=MAX_RADIUS_M)] = 500,
        failure_min: Annotated[float, Query(ge=0, le=MAX_FAILURE_MIN)] = 7.5,
        plan_id: UUID | None = None,
        from_kind: plans.Kind | None = None,
        from_name: PlaceName = None,
        from_osm: OsmId = None,
        to_kind: plans.Kind | None = None,
        to_name: PlaceName = None,
        to_osm: OsmId = None,
    ) -> PlanResponse:
        if from_station is None and (from_lat is None or from_lng is None):
            raise HTTPException(422, "give from_lat and from_lng, or from_station")
        start = None if from_station else (from_lat, from_lng)
        try:
            p = svc.plan(start, (to_lat, to_lng), from_station, radius_m, failure_min)
        except LookupError as e:
            raise HTTPException(422 if "station" in str(e) else 503, str(e)) from e
        now, chosen, requested = p["live"], p["pickup"], p["requested"]
        leave = now.captured_at + timedelta(minutes=chosen["walk_min"])
        candidates = [
            {
                **station(r),
                "rank": r["rank"],
                "recommendable": r["recommendable"],
                "walk_m": r["walk_m"],
                "walk_min": r["walk_min"],
                "ride_min": r["ride_min"],
                "ride_source": r["ride_source"],
                "arrive_at": leave + timedelta(minutes=r["ride_min"]),
                "p_full_at_arrival": r["p_full"],
                "p_free": r["p_free"],
                "expected_min": r["expected_min"],
                "outside_horizons": r["outside_horizons"],
            }
            for r in p["candidates"].to_dicts()
        ]
        response = PlanResponse(
            captured_at=now.captured_at,
            weather_missing=now.weather_missing,
            radius_m=radius_m,
            failure_min=failure_min,
            pickup=pickup(chosen),
            pickup_options=[pickup(o) for o in p["pickup_options"]],
            requested=station(requested) if requested else None,
            candidates=candidates,
        )
        client = request.client.host if request.client else ""
        save = plan_store and plan_id and saved_plans.first(str(plan_id))
        if save and plan_limit.allow(client):
            ends = {
                "from": plans.end(from_kind, from_name, from_osm, from_lat, from_lng),
                "to": plans.end(to_kind, to_name, to_osm, to_lat, to_lng),
            }
            record = plan_record(response, plan_id, ends, from_station)
            background.add_task(save_plan, record, now.captured_at)
        return response

    @app.post("/v1/feedback", status_code=204)
    def feedback(answer: Feedback, request: Request) -> None:
        if not limit.allow(request.client.host if request.client else ""):
            raise HTTPException(429, "too many answers; try later")
        now = datetime.now(UTC)
        if not now - FEEDBACK_MAX_AGE <= answer.captured_at <= now + timedelta(minutes=5):
            raise HTTPException(422, "the plan is too old")
        known = set(live_or_503().stations["station_id"].to_list())
        if not {answer.pickup_id, answer.dropoff_id} <= known:
            raise HTTPException(422, "unknown station")
        record = answer.model_dump(mode="json") | {"received_at": now.isoformat()}
        fb.write(sink, record, answer.captured_at)

    return app


app = make_app()
