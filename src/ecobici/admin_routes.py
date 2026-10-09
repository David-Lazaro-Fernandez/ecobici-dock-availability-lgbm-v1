"""HTTP routes of the ``/admin`` page. ``ecobici.admin`` has the data and the access rules."""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import duckdb
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ecobici import config
from ecobici.admin import Admin

PAGE = Path(__file__).with_name("admin.html")
DEFAULT_DAYS = 7
MAX_PLANS = 500
MAX_SQL = 5000
# The page loads no outside resources. It must not show inside another site.
PAGE_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
}

Day = Annotated[date | None, Query()]


class SqlQuery(BaseModel):
    sql: Annotated[str, Field(min_length=1, max_length=MAX_SQL)]


def window(since: date | None, until: date | None) -> tuple[date, date]:
    """Default: the last DEFAULT_DAYS days, local time."""
    today = datetime.now(config.LOCAL_TZ).date()
    return since or today - timedelta(days=DEFAULT_DAYS - 1), until or today


def router(admin: Admin) -> APIRouter:
    r = APIRouter(prefix="/admin")
    page = PAGE.read_text()

    @r.get("", response_class=HTMLResponse, include_in_schema=False)
    def show() -> HTMLResponse:
        return HTMLResponse(page, headers=PAGE_HEADERS)

    @r.get("/api/status", include_in_schema=False)
    def status() -> dict:
        admin.refresh()
        counts = admin.query(
            "select (select count(*) from plans) as plans,"
            " (select count(*) from feedback) as answers"
        )[0]
        return {"loaded_at": admin.loaded_at, "error": admin.error, **counts}

    @r.get("/api/demand", include_in_schema=False)
    def demand(since: Day = None, until: Day = None) -> dict:
        return admin.demand(*window(since, until))

    @r.get("/api/places", include_in_schema=False)
    def places(since: Day = None, until: Day = None) -> list[dict]:
        return admin.places(*window(since, until))

    @r.get("/api/feedback", include_in_schema=False)
    def answers(since: Day = None, until: Day = None) -> dict:
        return admin.answers(*window(since, until))

    @r.get("/api/plans", include_in_schema=False)
    def plan_list(
        since: Day = None,
        until: Day = None,
        kind: str | None = None,
        station: str | None = None,
        limit: Annotated[int, Query(ge=1, le=MAX_PLANS)] = 100,
    ) -> list[dict]:
        return admin.plan_list(*window(since, until), kind or None, station or None, limit)

    @r.post("/api/sql", include_in_schema=False)
    def sql(body: SqlQuery) -> dict:
        try:
            return admin.sql(body.sql)
        except (ValueError, duckdb.Error) as e:
            raise HTTPException(400, str(e).splitlines()[0]) from e

    return r
