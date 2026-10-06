"""M5 baselines (PRD: mandatory), fitted on train months only.

- ``p_persist``: the station stays as it is now (0/1), as the PRD defines it.
- ``p_persist_cal``: calibrated persistence, P(full at t+h | full now) per station,
  falling back to the global rate. A fairer reference for the skill score than 0/1.
- ``p_hist``: historical mean of "full" per station × arrival slot × day type, falling
  back to the station mean, then the global mean.
"""

import duckdb

from ecobici.eval.splits import TRAIN


def predict(con: duckdb.DuckDBPyConnection, horizon_min: int) -> str:
    """Create ``pred_{h}`` with every baseline for every example; return its name."""
    ex, out = f"ex_{horizon_min}", f"pred_{horizon_min}"
    con.execute(
        f"CREATE OR REPLACE TEMP TABLE train_{horizon_min} AS "
        f"SELECT * FROM {ex} WHERE month IN (SELECT unnest(?))",
        [list(TRAIN)],
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {out} AS
        WITH tr AS (SELECT * FROM train_{horizon_min}),
        g AS (SELECT avg(y::int) AS p FROM tr),
        g_now AS (SELECT full_now, avg(y::int) AS p FROM tr GROUP BY full_now),
        st_now AS (SELECT sid, full_now, avg(y::int) AS p, count(*) AS n
                   FROM tr GROUP BY sid, full_now),
        st AS (SELECT sid, avg(y::int) AS p FROM tr GROUP BY sid),
        cell AS (SELECT sid, target_slot, weekend, avg(y::int) AS p, count(*) AS n
                 FROM tr GROUP BY sid, target_slot, weekend)
        SELECT e.*,
               e.full_now::double AS p_persist,
               coalesce(CASE WHEN sn.n >= 20 THEN sn.p END, gn.p) AS p_persist_cal,
               coalesce(CASE WHEN c.n >= 10 THEN c.p END, s.p, (SELECT p FROM g)) AS p_hist
        FROM {ex} e
        LEFT JOIN st_now sn ON sn.sid = e.sid AND sn.full_now = e.full_now
        LEFT JOIN g_now gn ON gn.full_now = e.full_now
        LEFT JOIN st s ON s.sid = e.sid
        LEFT JOIN cell c ON c.sid = e.sid AND c.target_slot = e.target_slot
                        AND c.weekend = e.weekend
        """
    )
    return out
