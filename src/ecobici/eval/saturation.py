"""M3: is saturation real (V1), and do neighbours fail together (V6)?

Runs over the healthy MaxHalford months. "Full" follows ``labels``: installed,
accepting returns and zero free docks; out-of-service readings are excluded.
Neighbours are stations within the walkable radius (haversine × detour factor).
"""

import argparse
import sys
from pathlib import Path

import duckdb

from ecobici import config
from ecobici.ingest import maxhalford

PEAK_START_MIN = 8 * 60 + 30  # weekday morning arrival window, local time
PEAK_END_MIN = 10 * 60 + 30


def connect(files: list[Path]) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"SET TimeZone='{config.LOCAL_TZ.key}'")
    paths = [str(f) for f in files]
    con.execute(
        """
        CREATE TABLE r AS
        SELECT station_id AS sid, committed_at_utc AS t,
               (is_installed AND is_returning) AS ok,
               num_docks_available = 0 AS is_full,
               extract(hour FROM committed_at_utc) AS h,
               extract(hour FROM committed_at_utc) * 60
                   + extract(minute FROM committed_at_utc) AS minute_of_day,
               isodow(committed_at_utc) >= 6 AS weekend
        FROM read_parquet(?)
        """,
        [paths],
    )
    con.execute(
        """
        CREATE TABLE st AS
        SELECT station_id AS sid, any_value(name) AS sname,
               avg(latitude) AS lat, avg(longitude) AS lon, max(capacity) AS cap
        FROM read_parquet(?) GROUP BY 1
        """,
        [paths],
    )
    max_straight_m = config.WALK_RADIUS_M / config.WALK_DETOUR_FACTOR
    con.execute(
        """
        CREATE TABLE nb AS
        SELECT * FROM (
            SELECT a.sid AS a, b.sid AS b,
                   2 * 6371000 * asin(sqrt(
                       pow(sin(radians(b.lat - a.lat) / 2), 2)
                       + cos(radians(a.lat)) * cos(radians(b.lat))
                         * pow(sin(radians(b.lon - a.lon) / 2), 2))) AS d
            FROM st a JOIN st b ON a.sid <> b.sid
        ) WHERE d <= ?
        """,
        [max_straight_m],
    )
    return con


def v1(con: duckdb.DuckDBPyConnection, top: int = 15) -> dict:
    overall = con.execute("SELECT avg(is_full::int) FROM r WHERE ok").fetchone()[0]
    by_hour = con.execute(
        "SELECT h, avg(is_full::int) FROM r WHERE ok AND NOT weekend GROUP BY h ORDER BY h"
    ).fetchall()
    con.execute(
        """
        CREATE OR REPLACE TABLE peak AS
        SELECT sid, avg(is_full::int) AS f FROM r
        WHERE ok AND NOT weekend AND minute_of_day BETWEEN ? AND ?
        GROUP BY sid
        """,
        [PEAK_START_MIN, PEAK_END_MIN],
    )
    counts = con.execute(
        "SELECT count(*), sum((f >= .10)::int), sum((f >= .25)::int), sum((f >= .50)::int) "
        "FROM peak"
    ).fetchone()
    top_rows = con.execute(
        "SELECT sname, cap, f FROM peak JOIN st USING (sid) ORDER BY f DESC LIMIT ?", [top]
    ).fetchall()
    return {
        "overall_full_rate": overall,
        "weekday_by_hour": by_hour,
        "peak_stations": counts[0],
        "peak_ge_10": counts[1],
        "peak_ge_25": counts[2],
        "peak_ge_50": counts[3],
        "peak_top": top_rows,
    }


def v6(con: duckdb.DuckDBPyConnection) -> dict:
    con.execute("CREATE OR REPLACE TABLE rr AS SELECT sid, t, is_full FROM r WHERE ok")
    base = con.execute("SELECT avg(is_full::int) FROM rr").fetchone()[0]
    pair = con.execute(
        """
        WITH af AS (SELECT sid AS a, t FROM rr WHERE is_full)
        SELECT avg(rb.is_full::int),
               avg(CASE WHEN nb.d < 200 THEN rb.is_full::int END),
               avg(CASE WHEN nb.d >= 200 THEN rb.is_full::int END)
        FROM af JOIN nb ON nb.a = af.a JOIN rr rb ON rb.sid = nb.b AND rb.t = af.t
        """
    ).fetchone()
    group = con.execute(
        """
        WITH af AS (SELECT sid AS a, t FROM rr WHERE is_full),
        x AS (
            SELECT af.a, af.t, bool_and(rb.is_full) AS all_full, bool_or(rb.is_full) AS any_full
            FROM af JOIN nb ON nb.a = af.a JOIN rr rb ON rb.sid = nb.b AND rb.t = af.t
            GROUP BY 1, 2
        )
        SELECT avg(all_full::int), avg(any_full::int), count(*) FROM x
        """
    ).fetchone()
    with_nb = con.execute("SELECT count(DISTINCT a), count(*) FROM nb").fetchone()
    n_st = con.execute("SELECT count(*) FROM st").fetchone()[0]
    return {
        "base_full_rate": base,
        "p_b_full_given_a": pair[0],
        "p_b_full_given_a_lt200": pair[1],
        "p_b_full_given_a_ge200": pair[2],
        "p_all_neighbours_full": group[0],
        "p_any_neighbour_full": group[1],
        "full_events": group[2],
        "stations": n_st,
        "stations_with_neighbour": with_nb[0],
        "mean_neighbours": with_nb[1] / with_nb[0] if with_nb[0] else 0.0,
    }


def format_report(r1: dict, r6: dict) -> str:
    def pct(x):
        return "n/a" if x is None else f"{100 * x:.1f}%"

    lines = [
        "## V1 — saturation",
        f"- Overall full rate: {pct(r1['overall_full_rate'])}",
        "- Weekday full rate by hour: "
        + ", ".join(f"{int(h)}h {pct(f)}" for h, f in r1["weekday_by_hour"]),
        f"- Weekday 08:30–10:30: of {r1['peak_stations']} stations, {r1['peak_ge_10']} are full "
        f">=10% of the time, {r1['peak_ge_25']} >=25%, {r1['peak_ge_50']} >=50%",
        "- Most saturated at 08:30–10:30:",
        *(f"  - {name} (capacity {cap}): {pct(f)}" for name, cap, f in r1["peak_top"]),
        "",
        "## V6 — neighbours fail together",
        f"- Stations with a walkable neighbour: {r6['stations_with_neighbour']} of "
        f"{r6['stations']} (mean {r6['mean_neighbours']:.1f} neighbours)",
        f"- Base full rate: {pct(r6['base_full_rate'])}",
        f"- P(B full | A full): {pct(r6['p_b_full_given_a'])} "
        f"(<200 m: {pct(r6['p_b_full_given_a_lt200'])}, "
        f">=200 m: {pct(r6['p_b_full_given_a_ge200'])})",
        f"- When A is full: P(any neighbour full) {pct(r6['p_any_neighbour_full'])}, "
        f"P(all neighbours full) {pct(r6['p_all_neighbours_full'])} "
        f"over {r6['full_events']:,} full readings",
    ]
    return "\n".join(lines)


def healthy_files(root: Path) -> list[Path]:
    return [
        root / f"{r['month']}.parquet" for r in maxhalford.month_diagnostics(root) if r["healthy"]
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=maxhalford.DEFAULT_DIR)
    args = parser.parse_args(argv)
    con = connect(healthy_files(args.dir))
    print(format_report(v1(con), v6(con)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
