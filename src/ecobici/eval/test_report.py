"""Final test (next_steps.md, step 8): the frozen M6 model on the test months. Run it
once.

    uv run python -m ecobici.eval.test_report > docs/reports/M6_test_output.md

docs/reports/M6_test.md registers the protocol and the pass criteria. Do not tune
anything after the run.

- The model is trained again (training is deterministic). Before any score, its
  artifacts must be byte-identical to the frozen ones. The station list comes from the
  M6 files: stations that exist only in the test months are excluded.
- 2026-01 is the main test. 2026-09 starts at ``splits.TEST_FROM`` and is reported
  separately: with its 12-min cadence, the 15, 30 and 45-min labels are read at 12, 24
  and 48 min.
- The rolling recalibrations use only the past: VAL_REPORT for 2026-01. 2026-09 has no
  history before the 11th, so it starts with the static maps.
"""

import argparse
import sys
from pathlib import Path

import duckdb
import numpy as np
import polars as pl

from ecobici.eval import model_report as mr
from ecobici.eval.baseline_report import HORIZONS, is_saturated_peak
from ecobici.eval.splits import TEST, TEST_FROM, TRAIN, VALIDATION
from ecobici.features import model_matrix, targets
from ecobici.ingest import maxhalford, openmeteo
from ecobici.ingest import trips as trip_ingest

# CDMX is UTC−6 all year since 2022.
UTC_OFFSET = np.timedelta64(6, "h")


def local_midnight(day: str) -> np.datetime64:
    """Naive UTC instant of 00:00 CDMX on ``day`` (YYYY-MM-DD)."""
    return np.datetime64(f"{day}T00:00") + UTC_OFFSET


def month_start(month: str) -> str:
    y, m = map(int, month.split("-"))
    return f"{y + (m == 12)}-{m % 12 + 1:02d}-01"


def final_periods() -> tuple[mr.Period, ...]:
    history = mr.Period("VAL_REPORT", mr.REPORT_START, local_midnight("2026-01-01"), report=False)
    tests = tuple(
        mr.Period(
            m,
            local_midnight(TEST_FROM.get(m, f"{m}-01")),
            local_midnight(month_start(m)),
        )
        for m in TEST
    )
    return (history, *tests)


def fallback_share(report: pl.DataFrame, saturated: list[str]) -> float:
    """Share of saturated_peak rows calibrated by the static Platt map, not a weekly fit.
    The fallback gives exactly the static value, so equal values mark it."""
    sp = report.filter(is_saturated_peak(saturated))
    return float((sp["p_lgbm_sub_roll"] == sp["p_lgbm_sub"]).mean()) if sp.height else np.nan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=maxhalford.DEFAULT_DIR)
    parser.add_argument("--trips", type=Path, default=trip_ingest.DEFAULT_DIR)
    parser.add_argument("--weather", type=Path, default=openmeteo.DEFAULT_PATH)
    parser.add_argument("--raw", type=Path, default=Path("raw"))
    parser.add_argument("--frozen", type=Path, default=Path("artifacts"))
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts/test"))
    parser.add_argument("--horizons", type=int, nargs="+", default=list(HORIZONS))
    parser.add_argument("--duckdb-memory", default="10GB")
    parser.add_argument("--figures", type=Path, default=Path("docs/reports/figures"))
    args = parser.parse_args(argv)

    model_months = (*TRAIN, *VALIDATION)
    files = [args.dir / f"{m}.parquet" for m in (*model_months, *TEST)]
    files = [f for f in files if f.exists()]
    spill = Path("data/duckdb_tmp")
    spill.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(config={"memory_limit": args.duckdb_memory, "temp_directory": str(spill)})
    mr.log("loading snapshots (with test months), flows, weather")
    targets.load_snapshots(con, files)
    model_matrix.prepare_shared(
        con,
        mr.trip_flow(args.trips, args.raw),
        pl.read_parquet(args.weather),
        station_files=model_months,
    )
    unseen = con.execute(
        "SELECT count(DISTINCT sid) FROM snap WHERE file_month IN (SELECT unnest(?)) "
        "AND sid NOT IN (SELECT sid FROM stations)",
        [list(TEST)],
    ).fetchone()[0]
    mr.log(f"stations only in the test months (left out): {unseen}")

    periods = final_periods()
    center = mr.center_stations(con)
    results: dict[str, list[dict]] = {p.name: [] for p in periods if p.report}
    for h in args.horizons:
        reports, saturated, info = mr.fit_predict(
            con, h, args.artifacts, periods=periods, expect=args.frozen
        )
        for name, report in reports.items():
            r = {**mr.evaluate(report, saturated, center, h), **info}
            r["fallback_share"] = fallback_share(report, saturated)
            results[name].append(r)
        mr.log(f"h={h}: done")

    out = [f"Estaciones que solo aparecen en los meses de prueba (sin filas): {unseen}\n"]
    for name, res in results.items():
        p = next(p for p in periods if p.name == name)
        out.append(f"# Prueba: {name} ({p.start} → {p.end} UTC)\n")
        out.append(
            "Filas de saturadas + pico calibradas con el Platt fijo (sin ventana semanal): "
            + ", ".join(f"{r['horizon']} min {r['fallback_share']:.0%}" for r in res)
            + "\n"
        )
        out.append(mr.render(res, title=f"Resultados ({name})"))
        mr.plot_reliability(res, args.figures / f"M6_test_{name}.png", period=name)
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    np.seterr(all="ignore")
    sys.exit(main())
