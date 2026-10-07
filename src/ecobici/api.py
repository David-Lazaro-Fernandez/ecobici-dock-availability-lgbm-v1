"""HTTP API for the web app (``web/``): live station predictions and trip plans.

    uv run --extra api --extra model uvicorn ecobici.api:app --port 8000

Docs at http://localhost:8000/docs. Read-only, GET only, CORS for ECOBICI_API_ORIGINS
(comma-separated, default the Next dev server). The model, S3 fetch and predictions
live in ``ecobici.serve.LiveService``; this module only shapes requests and responses.
"""

import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

from ecobici.eval.baseline_report import HORIZONS
from ecobici.serve import LiveService

ORIGINS = os.environ.get("ECOBICI_API_ORIGINS", "http://localhost:3000").split(",")
MAX_RADIUS_M = 1500
MAX_FAILURE_MIN = 30


class Station(BaseModel):
    id: str
    code: str
    name: str
    lat: float
    lng: float
    capacity: int | None
    docks: int | None
    bikes: int | None
    state: str  # available | full | unavailable | stale
    # P(full) at 15 / 30 / 45 min, keyed by minutes; null when not predicted.
    p_full: dict[str, float] | None
    # P(no bike) at 15 min, keyed by minutes; null without the empty-station model.
    p_empty: dict[str, float] | None = None


class StationsResponse(BaseModel):
    captured_at: datetime
    weather_missing: bool
    horizons: list[int]
    stations: list[Station]


class Pickup(Station):
    walk_m: float
    walk_min: float
    # P(no bike left when you get there): 0 at the start station itself.
    p_empty_at_arrival: float | None
    # Walk + P(no bike) × failure cost + the best drop-off's expected minutes.
    total_min: float | None


class Candidate(Station):
    rank: int | None  # 1 = best; null when not recommendable (out of service or stale)
    recommendable: bool
    walk_m: float  # to the destination
    walk_min: float
    ride_min: float
    ride_source: str
    arrive_at: datetime
    p_full_at_arrival: float | None
    p_free: float | None
    expected_min: float | None  # from the pickup: ride + walk + P(full) × failure cost
    outside_horizons: bool


class PlanResponse(BaseModel):
    captured_at: datetime
    weather_missing: bool
    radius_m: float
    failure_min: float
    pickup: Pickup
    # The pickups compared, best total first (the first one is `pickup`).
    pickup_options: list[Pickup]
    # The start station asked for, when it had no bike to take (empty, out of service or
    # not reporting) and the pickup moved to the nearest station with one.
    requested: Station | None
    candidates: list[Candidate]


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


def make_app(service: LiveService | None = None) -> FastAPI:
    svc = service or LiveService()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Warm up in the background: loading the model takes ~20 s, and /health
        # should answer meanwhile.
        if service is None:
            threading.Thread(target=svc.current, daemon=True).start()
        yield

    app = FastAPI(title="Ecobici dock availability", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET"], allow_headers=["*"]
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
        to_lat: Annotated[float, Query(ge=-90, le=90)],
        to_lng: Annotated[float, Query(ge=-180, le=180)],
        from_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
        from_lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
        from_station: str | None = None,
        radius_m: Annotated[float, Query(gt=0, le=MAX_RADIUS_M)] = 500,
        failure_min: Annotated[float, Query(ge=0, le=MAX_FAILURE_MIN)] = 7.5,
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
        return PlanResponse(
            captured_at=now.captured_at,
            weather_missing=now.weather_missing,
            radius_m=radius_m,
            failure_min=failure_min,
            pickup=pickup(chosen),
            pickup_options=[pickup(o) for o in p["pickup_options"]],
            requested=station(requested) if requested else None,
            candidates=candidates,
        )

    return app


app = make_app()
