"""M6: train LightGBM per horizon and score it against the baselines.

    uv run python -m ecobici.eval.model_report

Train on TRAIN, early-stop and calibrate on VAL_FIT, report on VAL_REPORT. Test months
are never read. Targets (M5, approved): BSS > 0 vs the best baseline in every segment;
BSS >= 0.10 at 30 min on saturated_peak; |observed − predicted| <= 0.05 in every
calibration bin with n >= 1,000 on saturated_peak.
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import polars as pl

from ecobici import config
from ecobici.eval import metrics
from ecobici.eval.baseline_report import HORIZONS, saturated_stations, segments
from ecobici.eval.splits import TRAIN, VAL_FIT, VAL_REPORT, VALIDATION
from ecobici.features import model_matrix, targets
from ecobici.features import trips as trip_features
from ecobici.ingest import maxhalford, openmeteo
from ecobici.ingest import trips as trip_ingest
from ecobici.models import baselines, lgbm

BASELINES = ["p_persist", "p_persist_cal", "p_hist"]
# p_lgbm is the pre-registered model (one calibration on VAL_FIT). p_lgbm_recal adds
# weekly rolling recalibration, chosen after seeing drift in M6; confirm it on test.
MODELS = [*BASELINES, "p_lgbm_raw", "p_lgbm", "p_lgbm_recal"]
PRIMARY = "p_lgbm"
REPORT_START = np.datetime64("2025-10-01T06:00")  # 2025-10-01 00:00 CDMX, in UTC
TARGET_BSS_PRODUCT = 0.10
TARGET_CALIBRATION = 0.05
MIN_BIN_N = 1000


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def trip_flow(trips_dir: Path, raw_dir: Path) -> pl.DataFrame:
    from ecobici.devtools.stations import fetch_live, latest_information

    info = latest_information(raw_dir) or fetch_live(config.STATION_INFORMATION_URL)
    start, end = model_matrix.flow_window()
    tz = config.LOCAL_TZ
    loaded = trip_features.load(
        datetime(start.year, start.month, start.day, tzinfo=tz),
        datetime(end.year, end.month, end.day, tzinfo=tz),
        trip_ingest.station_code_map(info),
        trips_dir,
    )
    return trip_features.net_flow(loaded)


def center_stations(con: duckdb.DuckDBPyConnection) -> set[str]:
    """V8: 'center' = stations closer than the median distance to the system centroid."""
    rows = con.execute(
        """
        WITH c AS (SELECT avg(lat) AS lat, avg(lon) AS lon FROM stations),
        d AS (SELECT s.sid, pow(s.lat - c.lat, 2) + pow((s.lon - c.lon) * 0.94, 2) AS d2
              FROM stations s, c)
        SELECT sid FROM d WHERE d2 <= (SELECT median(d2) FROM d)
        """
    ).fetchall()
    return {r[0] for r in rows}


def calibration_gap(df: pl.DataFrame, model: str) -> tuple[float, pl.DataFrame]:
    rel = metrics.reliability(df, model).with_columns(
        gap=(pl.col("observed") - pl.col("predicted")).abs()
    )
    big = rel.filter(pl.col("n") >= MIN_BIN_N)
    return (big["gap"].max() if big.height else float("nan")), rel


def ece(df: pl.DataFrame, model: str) -> float:
    rel = metrics.reliability(df, model)
    return float(((rel["observed"] - rel["predicted"]).abs() * rel["n"]).sum() / rel["n"].sum())


def run_horizon(con, h: int, artifacts: Path) -> dict:
    log(f"h={h}: examples + baselines")
    targets.build_examples(con, h)
    baselines.predict(con, h)
    saturated = saturated_stations(con, h)
    log(f"h={h}: features")
    feat = model_matrix.build(con, h, source=f"pred_{h}")

    X, y, _ = lgbm.matrix(con, feat, TRAIN)
    Xf, yf, _ = lgbm.matrix(con, feat, VAL_FIT)
    log(f"h={h}: training on {len(y):,} rows, early stopping on {len(yf):,}")
    t0 = time.time()
    model = lgbm.train(X, y, Xf, yf)
    train_s = time.time() - t0
    del X, y, Xf, yf
    model.save(artifacts, h)

    # VAL_FIT rows are scored too, only as history for the rolling recalibration.
    Xr, yr, meta = lgbm.matrix(con, feat, (*VAL_FIT, *VAL_REPORT), extra=[*BASELINES, "t"])
    raw = model.predict_raw(Xr)
    del Xr
    times = meta["t"].dt.convert_time_zone("UTC").dt.replace_time_zone(None)
    recal = lgbm.rolling_recalibrate(times, raw, yr, score_from=REPORT_START)
    in_report = pl.Series(times.to_numpy() >= REPORT_START)
    report = meta.with_columns(
        p_lgbm_raw=pl.Series(raw),
        p_lgbm=pl.Series(model.calibrator.predict(raw)),
        p_lgbm_recal=pl.Series(recal),
    ).filter(in_report)
    for t in (f"ex_{h}", f"pred_{h}", f"feat_{h}", f"train_{h}"):
        con.execute(f"DROP TABLE IF EXISTS {t}")

    seg_rows, checks = [], []
    for name, seg in segments(report, saturated).items():
        s = metrics.summarize(seg, MODELS)
        best = s.filter(pl.col("model").is_in(BASELINES)).sort("brier").row(0, named=True)
        s = s.with_columns(
            segment=pl.lit(name),
            horizon=pl.lit(h),
            reference=pl.lit(best["model"]),
            bss=1 - pl.col("brier") / best["brier"],
        )
        seg_rows.append(s)
        for m in (PRIMARY, "p_lgbm_recal"):
            bss = s.filter(pl.col("model") == m)["bss"].item()
            checks.append((m, f"BSS > 0, {name}", bss, bss > 0))
            if name == "saturated_peak" and h == 30:
                ok = bss >= TARGET_BSS_PRODUCT
                checks.append((m, f"BSS >= {TARGET_BSS_PRODUCT}, saturated_peak", bss, ok))
    sat_peak = segments(report, saturated)["saturated_peak"]
    rel = {}
    for m in (PRIMARY, "p_lgbm_recal"):
        gap, rel[m] = calibration_gap(sat_peak, m)
        name = f"calibration gap <= {TARGET_CALIBRATION}, saturated_peak"
        checks.append((m, name, gap, gap <= TARGET_CALIBRATION))

    center = center_stations(con)
    is_center = pl.col("sid").is_in(list(center))
    v8 = {
        m: {
            "center": ece(report.filter(is_center), m),
            "periphery": ece(report.filter(~is_center), m),
        }
        for m in (PRIMARY, "p_lgbm_recal")
    }
    return {
        "horizon": h,
        "table": pl.concat(seg_rows),
        "checks": checks,
        "reliability": rel,
        "v8_ece": v8,
        "importance": lgbm.importance(model),
        "best_iteration": model.booster.best_iteration,
        "train_seconds": train_s,
    }


def render(results: list[dict]) -> str:
    out = ["## Resultados (validación, 2025-10 → 2025-12)\n"]
    out.append("| Horizon | Segment | n | Base rate | Model | Brier | BSS vs best baseline |")
    out.append("|---|---|---|---|---|---|---|")
    for r in results:
        for row in r["table"].iter_rows(named=True):
            mark = " (ref)" if row["model"] == row["reference"] else ""
            out.append(
                f"| {row['horizon']} min | {row['segment']} | {row['n']:,} | "
                f"{row['base_rate']:.3f} | {row['model']}{mark} | {row['brier']:.4f} | "
                f"{row['bss']:+.3f} |"
            )
    out.append(
        "\n## Metas\n\n| Horizon | Modelo | Meta | Valor | ¿Cumple? |\n|---|---|---|---|---|"
    )
    for r in results:
        for model, name, value, ok in r["checks"]:
            out.append(
                f"| {r['horizon']} min | {model} | {name} | {value:.3f} | {'✅' if ok else '❌'} |"
            )
    for r in results:
        for m, rel in r["reliability"].items():
            out.append(f"\n### {r['horizon']} min: calibración en saturated_peak ({m})\n")
            out.append("| Bin | n | Predicted | Observed |\n|---|---|---|---|")
            for b in rel.iter_rows(named=True):
                out.append(
                    f"| {b['bin']} | {b['n']:,} | {b['predicted']:.3f} | {b['observed']:.3f} |"
                )
        v8 = "; ".join(
            f"{m}: centro {e['center']:.4f}, periferia {e['periphery']:.4f}"
            for m, e in r["v8_ece"].items()
        )
        out.append(
            f"\nV8 (ECE, todas las estaciones): {v8}. "
            f"Árboles: {r['best_iteration']}; entrenamiento {r['train_seconds'] / 60:.1f} min."
        )
        out.append(
            "\nImportancia (ganancia): " + ", ".join(f"{f} {g:.1%}" for f, g in r["importance"])
        )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=maxhalford.DEFAULT_DIR)
    parser.add_argument("--trips", type=Path, default=trip_ingest.DEFAULT_DIR)
    parser.add_argument("--weather", type=Path, default=openmeteo.DEFAULT_PATH)
    parser.add_argument("--raw", type=Path, default=Path("raw"))
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--horizons", type=int, nargs="+", default=list(HORIZONS))
    parser.add_argument("--duckdb-memory", default="10GB")
    args = parser.parse_args(argv)

    months = [*TRAIN, *VALIDATION]  # test months stay unread
    files = [args.dir / f"{m}.parquet" for m in months if (args.dir / f"{m}.parquet").exists()]
    # Cap DuckDB and let it spill: by default it may take 80% of RAM, which starves
    # LightGBM and the rest of the machine.
    spill = Path("data/duckdb_tmp")
    spill.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(config={"memory_limit": args.duckdb_memory, "temp_directory": str(spill)})
    log("loading snapshots, flows, weather")
    targets.load_snapshots(con, files)
    model_matrix.prepare_shared(con, trip_flow(args.trips, args.raw), pl.read_parquet(args.weather))

    results = []
    for h in args.horizons:
        results.append(run_horizon(con, h, args.artifacts))
        log(f"h={h}: done")
    print(render(results))
    primary_ok = all(ok for r in results for m, _, _, ok in r["checks"] if m == PRIMARY)
    return 0 if primary_ok else 2


if __name__ == "__main__":
    np.seterr(all="ignore")
    sys.exit(main())
