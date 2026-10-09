"""Admin views of the plan and feedback logs, for the ``/admin`` page of the API.

The logs are where the API writes them: ``ECOBICI_PLAN_SINK`` and ``ECOBICI_FEEDBACK_SINK``.
An S3 sink is copied to ``ECOBICI_ADMIN_DIR`` (default ``data/logs``) at most once per
SYNC_EVERY. DuckDB then loads the local files into memory.

The API serves ``/admin`` only with ``ECOBICI_ADMIN=on``. It does not check a password:
Caddy protects ``/admin*`` with ``basic_auth``, and the API listens on 127.0.0.1 only
(``deploy/api/``).

After the load, DuckDB has no file access, a memory limit and a locked configuration, so the
SQL tab can only read the tables in memory: it cannot read ``api.env``.
"""

import os
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import duckdb
import polars as pl

from ecobici import config, plans
from ecobici import feedback as fb

ENABLE_ENV = "ECOBICI_ADMIN"
DIR_ENV = "ECOBICI_ADMIN_DIR"
DEFAULT_DIR = Path("data/logs")
SYNC_EVERY = timedelta(minutes=2)
SQL_MAX_ROWS = 1000
TOP_STATIONS = 15
DUCKDB_MEMORY = "256MB"
STATION_COLUMNS = ["id", "code", "name"]

# Explicit types: with inferred types, a field that is null in every file has no type.
PLAN_COLUMNS = {
    "plan_id": "VARCHAR",
    "captured_at": "TIMESTAMPTZ",
    "weather_missing": "BOOLEAN",
    "radius_m": "DOUBLE",
    "failure_min": "DOUBLE",
    "from": "STRUCT(kind VARCHAR, name VARCHAR, osm VARCHAR, lat DOUBLE, lng DOUBLE, "
    "station_id VARCHAR)",
    "to": "STRUCT(kind VARCHAR, name VARCHAR, osm VARCHAR, lat DOUBLE, lng DOUBLE)",
    "pickup_id": "VARCHAR",
    "requested_id": "VARCHAR",
    "pickups": "STRUCT(id VARCHAR, walk_m DOUBLE, walk_min DOUBLE, p_empty_at_arrival DOUBLE, "
    "total_min DOUBLE, walk_order INTEGER)[]",
    "candidates": "STRUCT(id VARCHAR, rank INTEGER, recommendable BOOLEAN, walk_m DOUBLE, "
    "walk_min DOUBLE, ride_min DOUBLE, ride_source VARCHAR, arrive_at TIMESTAMPTZ, "
    "p_full_at_arrival DOUBLE, p_free DOUBLE, expected_min DOUBLE, outside_horizons BOOLEAN, "
    "walk_order INTEGER)[]",
}
FEEDBACK_COLUMNS = {
    "kind": "VARCHAR",
    "plan_id": "VARCHAR",
    "captured_at": "TIMESTAMPTZ",
    "pickup_id": "VARCHAR",
    "dropoff_id": "VARCHAR",
    "rank": "INTEGER",
    "arrive_at": "TIMESTAMPTZ",
    "p_free": "DOUBLE",
    "p_empty_at_arrival": "DOUBLE",
    "useful": "BOOLEAN",
    "reason": "VARCHAR",
    "comment": "VARCHAR",
    "found_dock": "VARCHAR",
    "found_bike": "VARCHAR",
    "received_at": "TIMESTAMPTZ",
}


def enabled() -> bool:
    return os.environ.get(ENABLE_ENV) == "on"


@dataclass(frozen=True)
class Source:
    """Where a log is read: a local directory, or an S3 prefix copied to ``local``."""

    local: Path
    bucket: str | None = None
    prefix: str | None = None


def source(uri: str, cache: Path, name: str) -> Source:
    parsed = urlparse(uri)
    if parsed.scheme == "s3":
        return Source(cache / name, parsed.netloc, parsed.path.strip("/"))
    return Source(Path(parsed.path if parsed.scheme else uri))


def sync(client, src: Source) -> int:
    """Make ``src.local`` a copy of the S3 prefix. Return the number of files fetched.

    A feedback answer can replace an older one with the same size, so a file is fetched
    again when S3 has a newer one. Local files that are gone from S3 are deleted.
    """
    if src.bucket is None:
        return 0
    remote = {}
    for page in client.get_paginator("list_objects_v2").paginate(
        Bucket=src.bucket, Prefix=f"{src.prefix}/"
    ):
        for o in page.get("Contents", []):
            if o["Key"].endswith(".json.gz"):
                remote[o["Key"].removeprefix(f"{src.prefix}/")] = o
    fetched = 0
    for rel, o in remote.items():
        path = src.local / rel
        modified = o["LastModified"].timestamp()
        if path.exists() and path.stat().st_size == o["Size"] and path.stat().st_mtime >= modified:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        client.download_file(src.bucket, o["Key"], str(tmp))
        os.utime(tmp, (modified, modified))
        tmp.replace(path)
        fetched += 1
    for path in src.local.rglob("*.json.gz") if src.local.exists() else []:
        if str(path.relative_to(src.local)) not in remote:
            path.unlink()
    return fetched


def _quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _create(con, table: str, columns: dict[str, str], folder: Path) -> None:
    ddl = ", ".join(f'"{name}" {kind}' for name, kind in columns.items())
    con.execute(f"create table {table} ({ddl})")
    if not folder.exists() or not any(folder.rglob("*.json.gz")):
        return
    types = ", ".join(f"{_quote(name)}: {_quote(kind)}" for name, kind in columns.items())
    glob = _quote(str(folder / "**" / "*.json.gz"))
    con.execute(
        f"insert into {table} by name select * from read_json({glob}, columns = {{{types}}})"
    )


def load(plan_dir: Path, feedback_dir: Path, stations: pl.DataFrame | None):
    """An in-memory DuckDB with the tables ``plans``, ``candidates``, ``pickups``,
    ``feedback`` and ``stations``. ``local_at`` is the capture time in Mexico City."""
    con = duckdb.connect()
    _create(con, "raw_plans", PLAN_COLUMNS, plan_dir)
    _create(con, "feedback", FEEDBACK_COLUMNS, feedback_dir)
    con.execute(
        "create table plans as select *, timezone(?, captured_at) as local_at from raw_plans",
        [str(config.LOCAL_TZ)],
    )
    con.execute("drop table raw_plans")
    for table in ("candidates", "pickups"):
        con.execute(
            f"create table {table} as select plan_id, local_at, unnest({table}, recursive := true)"
            f" from plans"
        )
    names = (
        stations
        if stations is not None
        else pl.DataFrame(schema=dict.fromkeys(STATION_COLUMNS, pl.Utf8))
    )
    con.register("stations_view", names.select(STATION_COLUMNS))
    con.execute("create table stations as select * from stations_view")
    con.unregister("stations_view")
    con.execute(f"set memory_limit = '{DUCKDB_MEMORY}'")
    con.execute("set threads = 1")
    con.execute("set enable_external_access = false")
    con.execute("set lock_configuration = true")
    return con


def _rows(cursor) -> list[dict]:
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


class Admin:
    """The logs as DuckDB tables, reloaded at most once per SYNC_EVERY. Thread-safe."""

    def __init__(
        self,
        plan_uri: str | None = None,
        feedback_uri: str | None = None,
        cache: Path | None = None,
        stations=None,
        client=None,
    ):
        cache = cache or Path(os.environ.get(DIR_ENV, DEFAULT_DIR))
        plan_uri = plan_uri or os.environ.get(plans.SINK_ENV) or str(cache / "plans")
        feedback_uri = feedback_uri or os.environ.get(fb.SINK_ENV, fb.DEFAULT_SINK)
        self.plans = source(plan_uri, cache, "plans")
        self.feedback = source(feedback_uri, cache, "feedback")
        self.stations = stations
        self.client = client
        self.error: str | None = None
        self.loaded_at: datetime | None = None
        self._con = None
        self._lock = threading.Lock()

    def _s3(self):
        if self.client is None:
            import boto3

            self.client = boto3.client("s3")
        return self.client

    def refresh(self, force: bool = False) -> None:
        with self._lock:
            now = datetime.now(UTC)
            if not force and self.loaded_at and now - self.loaded_at < SYNC_EVERY:
                return
            try:
                for src in (self.plans, self.feedback):
                    if src.bucket:
                        sync(self._s3(), src)
                self.error = None
            # Any AWS or network error: keep the last copy.
            except Exception as e:  # noqa: BLE001
                self.error = f"S3 sync failed: {e}"
            names = self.stations() if self.stations else None
            try:
                self._con = load(self.plans.local, self.feedback.local, names)
            # A bad file: keep the last tables, if there are some.
            except duckdb.Error as e:
                self.error = f"load failed: {e}"
                if self._con is None:
                    raise
            self.loaded_at = now

    def query(self, sql: str, params: list | None = None) -> list[dict]:
        self.refresh()
        return _rows(self._con.cursor().execute(sql, params or []))

    def sql(self, text: str) -> dict:
        """One read-only SELECT from the SQL tab. At most SQL_MAX_ROWS rows."""
        self.refresh()
        statements = self._con.extract_statements(text)
        if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
            raise ValueError("give one SELECT statement")
        cursor = self._con.cursor().execute(text)
        names = [d[0] for d in cursor.description]
        rows = cursor.fetchmany(SQL_MAX_ROWS + 1)
        return {
            "columns": names,
            "rows": [list(r) for r in rows[:SQL_MAX_ROWS]],
            "truncated": len(rows) > SQL_MAX_ROWS,
        }

    # --- Views of the page -------------------------------------------------------
    def demand(self, since: date, until: date) -> dict:
        window = "local_at::date between ? and ?"
        args = [since, until]
        top = f"""
            select s.id, coalesce(any_value(st.name), s.id) as name, count(*) as plans
            from ({{}}) s left join stations st on st.id = s.id
            group by s.id order by plans desc limit {TOP_STATIONS}
        """
        best = f"select id from candidates where rank = 1 and {window}"
        return {
            "per_day": self.query(
                f"select local_at::date as day, count(*) as plans from plans where {window}"
                " group by day order by day",
                args,
            ),
            "per_hour": self.query(
                f"select hour(local_at) as hour, count(*) as plans from plans where {window}"
                " group by hour order by hour",
                args,
            ),
            "ends": self.query(
                f"""select 'from' as side, "from".kind as kind, count(*) as plans
                from plans where {window} group by kind
                union all
                select 'to', "to".kind, count(*) from plans where {window} group by "to".kind
                order by side, plans desc""",
                args + args,
            ),
            "pickups": self.query(
                top.format(f"select pickup_id as id from plans where {window}"), args
            ),
            "dropoffs": self.query(top.format(best), args),
        }

    def places(self, since: date, until: date) -> list[dict]:
        """Photon places picked as an end of a trip: the places missing from lugares.json."""
        return self.query(
            """
            with ends as (
                select local_at, "from" as place from plans
                union all select local_at, "to" from plans
            )
            select place.name as name, place.osm as osm, any_value(place.lat) as lat,
                any_value(place.lng) as lng, count(*) as plans, max(local_at) as last_at
            from ends
            where place.kind = 'photon' and local_at::date between ? and ?
            group by place.name, place.osm order by plans desc, last_at desc
            """,
            [since, until],
        )

    def answers(self, since: date, until: date) -> dict:
        window = "timezone(?, captured_at)::date between ? and ?"
        args = [str(config.LOCAL_TZ), since, until]
        return {
            "ratings": self.query(
                f"select useful, reason, count(*) as answers from feedback"
                f" where kind = 'rating' and {window} group by all order by answers desc",
                args,
            ),
            "trips": self.query(
                f"select found_dock, found_bike, count(*) as answers from feedback"
                f" where kind = 'trip' and {window} group by all order by answers desc",
                args,
            ),
            "comments": self.query(
                f"""select timezone(?, received_at) as at, useful, reason, comment, plan_id
                from feedback where comment is not null and {window}
                order by received_at desc limit 100""",
                [str(config.LOCAL_TZ), *args],
            ),
        }

    def plan_list(
        self, since: date, until: date, kind: str | None, station: str | None, limit: int
    ) -> list[dict]:
        """The newest plans first. ``kind`` matches either end; ``station`` the pickup or the
        best drop-off."""
        return self.query(
            """
            with best as (select plan_id, id, p_free from candidates where rank = 1),
            trip as (select plan_id, found_dock, found_bike from feedback where kind = 'trip'),
            rating as (select plan_id, useful from feedback where kind = 'rating')
            select p.plan_id, p.local_at, p."from".kind as from_kind, p."from".name as from_name,
                p."to".kind as to_kind, p."to".name as to_name,
                p.pickup_id, ps.name as pickup_name, b.id as dropoff_id, bs.name as dropoff_name,
                b.p_free, len(p.candidates) as candidates,
                r.useful, t.found_dock, t.found_bike
            from plans p
            left join best b using (plan_id)
            left join stations ps on ps.id = p.pickup_id
            left join stations bs on bs.id = b.id
            left join trip t using (plan_id)
            left join rating r using (plan_id)
            where p.local_at::date between ? and ?
                and (?::varchar is null or ? in (p."from".kind, p."to".kind))
                and (?::varchar is null or ? in (p.pickup_id, b.id))
            order by p.local_at desc limit ?
            """,
            [since, until, kind, kind, station, station, limit],
        )
