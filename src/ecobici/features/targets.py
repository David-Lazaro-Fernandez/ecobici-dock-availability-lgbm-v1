"""Examples (station, t, horizon) → target state at t + horizon, from snapshots.

The label is the first snapshot within ±``tolerance`` of t + h (M2: the cadence is
~15 min, so 7.5 min stays inside one slot). Rows out of service at t or at t + h are
removed: "full" must not stand for an outage.

``target`` sets the predicted state:

- ``full`` (M6, the frozen model): no free dock. In service: installed and returning.
- ``empty``: no bike to take. In service: installed only. In MaxHalford, ``is_renting``
  is false on almost all empty readings, so it marks "no bikes", not an outage.

The names keep "full" (``is_full``, ``full_now``, ``full_lag15``, ``nb_full_frac``…)
because they are in the frozen booster. For ``empty``, they mean "empty".
"""

from pathlib import Path

import duckdb

from ecobici import config

TOLERANCE_MIN = 7.5
TARGETS = {
    # (in service, target state)
    "full": ("(is_installed AND is_returning)", "num_docks_available = 0"),
    "empty": ("is_installed", "num_bikes_available = 0"),
}


def load_snapshots(con: duckdb.DuckDBPyConnection, files: list[Path], target: str = "full") -> None:
    """Table ``snap``: one row per (station, snapshot) with state and local calendar.
    ``is_full`` and ``ok`` follow ``target`` (see the module docstring)."""
    ok, state = TARGETS[target]
    con.execute(f"SET TimeZone='{config.LOCAL_TZ.key}'")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE snap AS
        SELECT station_id AS sid,
               committed_at_utc AS t,
               strftime(committed_at_utc, '%Y-%m') AS month,
               {ok} AS ok,
               {state} AS is_full,
               num_docks_available AS docks,
               num_bikes_available AS bikes,
               num_docks_disabled AS docks_disabled,
               capacity,
               latitude AS lat,
               longitude AS lon,
               -- The file a row came from (UTC month), so a table can be fitted on
               -- the same files whatever else is loaded.
               regexp_extract(filename, '(\\d{{4}}-\\d{{2}})\\.parquet$', 1) AS file_month
        FROM read_parquet(?, filename = true)
        """,
        [[str(f) for f in files]],
    )


def example_cols(horizon_min: int) -> str:
    """The columns an example knows at t (``now`` is a snap row). Training examples and
    live predictions share them."""
    return f"""now.sid, now.t, now.month,
               (extract(hour FROM now.t) * 60 + extract(minute FROM now.t)) // 15 AS slot,
               -- Slot and day type at *arrival* (t + h): where the dock is contested.
               (extract(hour FROM now.t + INTERVAL ({horizon_min}) MINUTE) * 60
                + extract(minute FROM now.t + INTERVAL ({horizon_min}) MINUTE)) // 15
                   AS target_slot,
               isodow(now.t + INTERVAL ({horizon_min}) MINUTE) >= 6 AS weekend,
               now.is_full AS full_now,
               now.docks AS docks_now,
               now.capacity"""


def build_examples(
    con: duckdb.DuckDBPyConnection, horizon_min: int, tolerance_min: float = TOLERANCE_MIN
) -> None:
    """Table ``ex_{h}``: sid, t, month, slot, target_slot, weekend (at arrival),
    full_now, docks_now, capacity, y. The label is the first reading within
    ±``tolerance_min`` of t + h (7.5 for ~15-min readings; ~1 for the 2-min captures)."""
    h_s, tol_s = horizon_min * 60, int(tolerance_min * 60)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE ex_{horizon_min} AS
        WITH now AS (
            SELECT *, t + INTERVAL ({h_s - tol_s}) SECOND AS lo
            FROM snap WHERE ok
        )
        SELECT {example_cols(horizon_min)},
               fut.is_full AS y
        FROM now
        ASOF JOIN snap fut ON fut.sid = now.sid AND fut.t >= now.lo
        WHERE fut.t <= now.t + INTERVAL ({h_s + tol_s}) SECOND
          AND fut.ok
        """
    )


def build_now(con: duckdb.DuckDBPyConnection, horizon_min: int, at) -> str:
    """Table ``now_{h}``: like ``ex_{h}``, for each in-service station at the snapshot
    ``at``, with no label (y is NULL). Return its name."""
    out = f"now_{horizon_min}"
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {out} AS
        SELECT {example_cols(horizon_min)}, NULL::BOOLEAN AS y
        FROM snap now WHERE now.ok AND now.t = ?
        """,
        [at],
    )
    return out
