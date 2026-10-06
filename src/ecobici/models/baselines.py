"""M5 baselines (PRD: mandatory), fitted on train months only.

- ``p_persist``: the station stays as it is now (0/1), as the PRD defines it.
- ``p_persist_cal``: calibrated persistence, P(full at t+h | full now) per station,
  falling back to the global rate. A fairer reference for the skill score than 0/1.
- ``p_hist``: historical mean of "full" per station × arrival slot × day type, falling
  back to the station mean, then the global mean.

``refits`` adds the fitted baselines again under a suffix, fitted on other months
(e.g. ``{"_tvf": (*TRAIN, *VAL_FIT)}``), so the model can be compared against
baselines that saw data as recent as its own calibration.
"""

import duckdb

from ecobici.eval.splits import TRAIN

FITTED = ("p_persist_cal", "p_hist")


def _fitted(ex: str, months: tuple[str, ...], k: str, suffix: str) -> tuple[str, str, str]:
    """(CTEs, select expressions, joins) for the fitted baselines on ``months``."""
    in_months = "month IN (" + ", ".join(f"'{m}'" for m in months) + ")"
    ctes = f"""
        tr{k} AS (SELECT sid, full_now, target_slot, weekend, y FROM {ex} WHERE {in_months}),
        g{k} AS (SELECT avg(y::int) AS p FROM tr{k}),
        g_now{k} AS (SELECT full_now, avg(y::int) AS p FROM tr{k} GROUP BY full_now),
        st_now{k} AS (SELECT sid, full_now, avg(y::int) AS p, count(*) AS n
                      FROM tr{k} GROUP BY sid, full_now),
        st{k} AS (SELECT sid, avg(y::int) AS p FROM tr{k} GROUP BY sid),
        cell{k} AS (SELECT sid, target_slot, weekend, avg(y::int) AS p, count(*) AS n
                    FROM tr{k} GROUP BY sid, target_slot, weekend)"""
    cols = f"""
        coalesce(CASE WHEN sn{k}.n >= 20 THEN sn{k}.p END, gn{k}.p) AS p_persist_cal{suffix},
        coalesce(CASE WHEN c{k}.n >= 10 THEN c{k}.p END, s{k}.p, (SELECT p FROM g{k}))
            AS p_hist{suffix}"""
    joins = f"""
        LEFT JOIN st_now{k} sn{k} ON sn{k}.sid = e.sid AND sn{k}.full_now = e.full_now
        LEFT JOIN g_now{k} gn{k} ON gn{k}.full_now = e.full_now
        LEFT JOIN st{k} s{k} ON s{k}.sid = e.sid
        LEFT JOIN cell{k} c{k} ON c{k}.sid = e.sid AND c{k}.target_slot = e.target_slot
                              AND c{k}.weekend = e.weekend"""
    return ctes, cols, joins


def predict(
    con: duckdb.DuckDBPyConnection,
    horizon_min: int,
    refits: dict[str, tuple[str, ...]] | None = None,
) -> str:
    """Create ``pred_{h}`` with every baseline for every example; return its name."""
    ex, out = f"ex_{horizon_min}", f"pred_{horizon_min}"
    # Train rows only; saturated_stations() reads this table too.
    con.execute(
        f"CREATE OR REPLACE TEMP TABLE train_{horizon_min} AS "
        f"SELECT * FROM {ex} WHERE month IN (SELECT unnest(?))",
        [list(TRAIN)],
    )
    fits = {"": TRAIN, **(refits or {})}
    parts = [_fitted(ex, months, str(i), sfx) for i, (sfx, months) in enumerate(fits.items())]
    ctes = ",".join(p[0] for p in parts)
    cols = ",".join(p[1] for p in parts)
    joins = "".join(p[2] for p in parts)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {out} AS
        WITH {ctes}
        SELECT e.*, e.full_now::double AS p_persist, {cols}
        FROM {ex} e {joins}
        """
    )
    return out
