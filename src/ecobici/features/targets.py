"""Examples (station, t, horizon) → full at t + horizon, from MaxHalford snapshots.

The target is the station's state at the first snapshot within ±``tolerance`` of
t + h (M2: cadence ~15 min, so 7.5 min keeps it inside one slot). Readings where the
station is out of service at either end are dropped: "full" must never stand in for
an outage. Built in DuckDB; one row per example.
"""

from pathlib import Path

import duckdb

from ecobici import config

TOLERANCE_MIN = 7.5


def load_snapshots(con: duckdb.DuckDBPyConnection, files: list[Path]) -> None:
    """Table ``snap``: one row per (station, snapshot) with state and local calendar."""
    con.execute(f"SET TimeZone='{config.LOCAL_TZ.key}'")
    con.execute(
        """
        CREATE OR REPLACE TABLE snap AS
        SELECT station_id AS sid,
               committed_at_utc AS t,
               strftime(committed_at_utc, '%Y-%m') AS month,
               (is_installed AND is_returning) AS ok,
               num_docks_available = 0 AS is_full,
               num_docks_available AS docks,
               num_bikes_available AS bikes,
               num_docks_disabled AS docks_disabled,
               capacity,
               latitude AS lat,
               longitude AS lon
        FROM read_parquet(?)
        """,
        [[str(f) for f in files]],
    )


def build_examples(con: duckdb.DuckDBPyConnection, horizon_min: int) -> None:
    """Table ``ex_{h}``: sid, t, month, slot, target_slot, weekend (at arrival),
    full_now, docks_now, capacity, y."""
    h_s, tol_s = horizon_min * 60, int(TOLERANCE_MIN * 60)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE ex_{horizon_min} AS
        WITH now AS (
            SELECT *, t + INTERVAL ({h_s - tol_s}) SECOND AS lo
            FROM snap WHERE ok
        )
        SELECT now.sid, now.t, now.month,
               (extract(hour FROM now.t) * 60 + extract(minute FROM now.t)) // 15 AS slot,
               -- Slot and day type at *arrival* (t + h): where the dock is contested.
               (extract(hour FROM now.t + INTERVAL ({horizon_min}) MINUTE) * 60
                + extract(minute FROM now.t + INTERVAL ({horizon_min}) MINUTE)) // 15
                   AS target_slot,
               isodow(now.t + INTERVAL ({horizon_min}) MINUTE) >= 6 AS weekend,
               now.is_full AS full_now,
               now.docks AS docks_now,
               now.capacity,
               fut.is_full AS y
        FROM now
        ASOF JOIN snap fut ON fut.sid = now.sid AND fut.t >= now.lo
        WHERE fut.t <= now.t + INTERVAL ({h_s + tol_s}) SECOND
          AND fut.ok
        """
    )
