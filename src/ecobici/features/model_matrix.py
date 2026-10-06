"""M6 feature matrix, built in DuckDB on top of ``snap`` and ``ex_{h}``.

Every feature uses only what is known at prediction time t (or, for weather, the
forecast for the next hour, which Open-Meteo serves at t too). Historical profiles
(trip flows, station rates) are fitted on train months only and joined onto every
split, so validation and test never inform them.
"""

from datetime import date

import duckdb
import polars as pl

from ecobici.calendar import HOLIDAYS
from ecobici.eval.splits import TRAIN

NEIGHBOUR_RADIUS_M = 300  # PRD: neighbour occupancy "a unos 300 m"
LAGS_MIN = (15, 30, 60)
LAG_TOLERANCE_MIN = 7.5

FEATURES = [
    # station identity and size
    "station",
    "capacity",
    # state now
    "docks_now",
    "bikes_now",
    "docks_disabled",
    "occupancy_now",
    # recent trend
    *[f"docks_lag{lag}" for lag in LAGS_MIN],
    *[f"docks_delta{lag}" for lag in LAGS_MIN],
    *[f"full_lag{lag}" for lag in LAGS_MIN],
    # neighbours at t
    "nb_n",
    "nb_full_frac",
    "nb_occupancy_mean",
    "nb_docks_sum",
    # calendar
    "minute_of_day",
    "target_slot",
    "weekday",
    "weekend",
    "holiday",
    # weather
    "precip_now",
    "precip_next_hour",
    "temperature_now",
    # historical trip flow (train window)
    "flow_arrivals_target",
    "flow_departures_target",
    "flow_net_target",
    "flow_net_window",
    # historical station profile (train window)
    "st_full_rate",
    "st_peak_full_rate",
]
CATEGORICAL = ["station"]


def prepare_shared(
    con: duckdb.DuckDBPyConnection, flow: pl.DataFrame, weather: pl.DataFrame
) -> None:
    """Per-snapshot neighbour state, weather, flows, station profiles and holidays."""
    con.register("flow_src", flow.to_arrow())
    con.register("weather_src", weather.to_arrow())
    con.register(
        "holiday_src", pl.DataFrame({"d": sorted(HOLIDAYS)}, schema={"d": pl.Date}).to_arrow()
    )
    con.execute("CREATE OR REPLACE TABLE flow AS SELECT * FROM flow_src")
    # Net flow summed over the slots *before* each slot, on a full 96-slot grid, so the
    # expected net arrivals between now and arrival are two lookups, not a range join.
    con.execute(
        """
        CREATE OR REPLACE TABLE flow_cum AS
        WITH grid AS (
            SELECT k.station_id, k.weekend, s.slot
            FROM (SELECT DISTINCT station_id, weekend FROM flow) k,
                 range(96) s(slot)
        )
        SELECT g.station_id, g.weekend, g.slot,
               coalesce(sum(coalesce(f.net_flow_mean, 0)) OVER (
                   PARTITION BY g.station_id, g.weekend ORDER BY g.slot
                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS cum_before,
               sum(coalesce(f.net_flow_mean, 0)) OVER (
                   PARTITION BY g.station_id, g.weekend) AS day_total
        FROM grid g
        LEFT JOIN flow f ON f.station_id = g.station_id AND f.weekend = g.weekend
                        AND f.slot = g.slot
        """
    )
    con.execute("CREATE OR REPLACE TABLE holidays AS SELECT d FROM holiday_src")
    con.execute(
        """
        CREATE OR REPLACE TABLE weather AS
        SELECT time_utc AS hour, precipitation AS precip, temperature_2m AS temp
        FROM weather_src
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE stations AS
        SELECT sid, avg(lat) AS lat, avg(lon) AS lon,
               row_number() OVER (ORDER BY sid) - 1 AS station
        FROM snap GROUP BY sid
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE nb AS
        SELECT a.sid AS a, b.sid AS b FROM stations a JOIN stations b ON a.sid <> b.sid
        WHERE 2 * 6371000 * asin(sqrt(
                  pow(sin(radians(b.lat - a.lat) / 2), 2)
                  + cos(radians(a.lat)) * cos(radians(b.lat))
                    * pow(sin(radians(b.lon - a.lon) / 2), 2))) <= ?
        """,
        [NEIGHBOUR_RADIUS_M],
    )
    # Snapshots are global commits, so neighbours share the exact timestamp.
    con.execute(
        """
        CREATE OR REPLACE TABLE nbf AS
        SELECT nb.a AS sid, s.t,
               count(*) AS nb_n,
               avg((s.ok AND s.is_full)::int) AS nb_full_frac,
               avg(1 - s.docks / nullif(s.capacity, 0)) AS nb_occupancy_mean,
               sum(s.docks) AS nb_docks_sum
        FROM nb JOIN snap s ON s.sid = nb.b
        GROUP BY ALL
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE st_profile AS
        SELECT sid,
               avg(is_full::int) FILTER (WHERE ok) AS st_full_rate,
               avg(is_full::int) FILTER (
                   WHERE ok AND isodow(t) < 6
                     AND extract(hour FROM t) * 60 + extract(minute FROM t)
                         BETWEEN 510 AND 630) AS st_peak_full_rate
        FROM snap WHERE month IN (SELECT unnest(?))
        GROUP BY sid
        """,
        [list(TRAIN)],
    )


def build(con: duckdb.DuckDBPyConnection, horizon_min: int, source: str | None = None) -> str:
    """Create ``feat_{h}``: the source's columns (``ex_{h}`` by default, or e.g.
    ``pred_{h}`` to carry baseline predictions along) plus FEATURES."""
    ex, out = source or f"ex_{horizon_min}", f"feat_{horizon_min}"
    lag_joins, lag_cols = [], []
    for lag in LAGS_MIN:
        a = f"l{lag}"
        max_gap = int((lag + LAG_TOLERANCE_MIN) * 60)
        lag_joins.append(
            f"ASOF LEFT JOIN snap {a} ON {a}.sid = e.sid "
            f"AND {a}.t <= e.t - INTERVAL ({lag * 60}) SECOND"
        )
        ok = f"({a}.t >= e.t - INTERVAL ({max_gap}) SECOND AND {a}.ok)"
        lag_cols += [
            f"CASE WHEN {ok} THEN {a}.docks END AS docks_lag{lag}",
            f"CASE WHEN {ok} THEN e.docks_now - {a}.docks END AS docks_delta{lag}",
            f"CASE WHEN {ok} THEN {a}.is_full::int END AS full_lag{lag}",
        ]
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {out} AS
        SELECT e.*,
               st.station,
               cur.bikes AS bikes_now,
               cur.docks_disabled,
               1 - e.docks_now / nullif(e.capacity, 0) AS occupancy_now,
               {", ".join(lag_cols)},
               coalesce(nbf.nb_n, 0) AS nb_n,
               nbf.nb_full_frac, nbf.nb_occupancy_mean, nbf.nb_docks_sum,
               extract(hour FROM e.t) * 60 + extract(minute FROM e.t) AS minute_of_day,
               isodow(e.t + INTERVAL ({horizon_min}) MINUTE) AS weekday,
               (CAST(e.t + INTERVAL ({horizon_min}) MINUTE AS DATE) IN (SELECT d FROM holidays))
                   AS holiday,
               w0.precip AS precip_now, w1.precip AS precip_next_hour, w0.temp AS temperature_now,
               ft.arrivals_mean AS flow_arrivals_target,
               ft.departures_mean AS flow_departures_target,
               ft.net_flow_mean AS flow_net_target,
               coalesce(CASE WHEN e.target_slot >= e.slot
                             THEN c1.cum_before - c0.cum_before
                             ELSE c0.day_total - c0.cum_before + c1.cum_before END, 0)
                   AS flow_net_window,
               sp.st_full_rate, sp.st_peak_full_rate
        FROM {ex} e
        JOIN stations st ON st.sid = e.sid
        JOIN snap cur ON cur.sid = e.sid AND cur.t = e.t
        {" ".join(lag_joins)}
        LEFT JOIN nbf ON nbf.sid = e.sid AND nbf.t = e.t
        LEFT JOIN weather w0 ON w0.hour = date_trunc('hour', e.t)
        LEFT JOIN weather w1 ON w1.hour = date_trunc('hour', e.t) + INTERVAL 1 HOUR
        LEFT JOIN flow ft ON ft.station_id = e.sid AND ft.slot = e.target_slot
                         AND ft.weekend = e.weekend
        -- Expected net arrivals from now until arrival: slots [slot, target_slot),
        -- wrapping past midnight.
        LEFT JOIN flow_cum c0 ON c0.station_id = e.sid AND c0.weekend = e.weekend
                             AND c0.slot = e.slot
        LEFT JOIN flow_cum c1 ON c1.station_id = e.sid AND c1.weekend = e.weekend
                             AND c1.slot = e.target_slot
        LEFT JOIN st_profile sp ON sp.sid = e.sid
        """
    )
    return out


def flow_window() -> tuple[date, date]:
    """Trip-flow fitting window: the train months, [first day, day after last month)."""
    first, last = TRAIN[0], TRAIN[-1]
    y, m = map(int, last.split("-"))
    end = date(y + (m == 12), m % 12 + 1, 1)
    return date.fromisoformat(f"{first}-01"), end
