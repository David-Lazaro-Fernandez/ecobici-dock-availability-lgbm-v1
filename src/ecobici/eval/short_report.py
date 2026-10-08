"""Short-horizon models (5 and 10 min) on the own 2-min captures, stacked on the 15-min
model.

    uv run python -m ecobici.ingest.capture_snapshots
    uv run python -m ecobici.eval.short_report --target empty --horizons 5 10

MaxHalford reads every ~15 min, so only the own captures show the state 5 min later. The
captures are new, so the model learns only a correction: the 15-min prediction is an
input, together with 2, 4 and 10-min lags.

Protocol:
- Examples from the captures only. The label is the reading at t + h ± 1 min.
- Days in order: 60 % train, 20 % early stopping and calibration, 20 % report. The dev
  day 2026-10-06 is never reported.
- Baselines: calibrated persistence (station × state now), the 15-min model, and the
  planner heuristic.
- With fewer than MIN_REPORT_WEEKDAYS report weekdays, the run is a DRY RUN. It saves
  nothing, and its numbers are not evidence.
"""

import argparse
import sys
from datetime import timedelta
from pathlib import Path

import duckdb
import numpy as np
import polars as pl

from ecobici import config, live
from ecobici.eval import bootstrap, metrics
from ecobici.eval.baseline_report import is_peak, is_saturated_peak
from ecobici.eval.model_report import log, trip_flow
from ecobici.features import model_matrix, targets
from ecobici.ingest import capture_snapshots, openmeteo
from ecobici.ingest import trips as trip_ingest
from ecobici.models import lgbm

LAGS = (2, 4, 10, 15, 30, 60)
# Label and lag windows at the 2-min cadence.
TOLERANCE_MIN = 1.0
BASE_H = 15
# Cumulative day shares: train | fit | report.
SPLIT = (0.6, 0.8)
MIN_REPORT_WEEKDAYS = 5
DEV_DAYS = ("2026-10-06",)
N_BOOT = 1000
MIN_BIN_N = 1000
BASE_ARTIFACTS = {"full": Path("artifacts"), "empty": Path("artifacts/empty")}
MODELS = ["p_persist_cal", "p_base", "p_planner", "p_short"]
FEATURES = [*model_matrix.features(LAGS), "p_base"]
# The first capture reading.
OWN_T0 = "(SELECT t0 FROM own_start)"


def split(days: list[str]) -> tuple[dict[str, str], bool]:
    """Each local day → train, fit or report, in order. Dev days only train. With fewer
    than 3 usable days, ``by_day`` is False: the caller splits by time, as a dry run."""
    ordered = sorted(days)
    usable = [d for d in ordered if d not in DEV_DAYS]
    parts = {d: "train" for d in ordered if d in DEV_DAYS}
    if len(usable) < 3:
        return parts | {d: "train" for d in usable}, False
    a, b = (max(1, round(len(usable) * s)) for s in SPLIT)
    b = min(max(b, a + 1), len(usable) - 1)
    for i, d in enumerate(usable):
        parts[d] = "train" if i < a else "fit" if i < b else "report"
    return parts, True


def planner_heuristic(now: pl.Expr, p_base: pl.Expr, h: int) -> pl.Expr:
    """The planner method for horizons under 15 min: linear from the state now (1 or 0)
    to the 15-min prediction."""
    w = min(h / BASE_H, 1.0)
    return now + (p_base - now) * w


def weather_for(days: list[str]) -> pl.DataFrame:
    """Historical forecasts for the capture days (the training source), plus the live
    forecast for the last hours."""
    lat, lon = config.WEATHER_POINT
    first, last = (np.datetime64(d).astype(object) for d in (min(days), max(days)))
    frames = [pl.read_parquet(openmeteo.DEFAULT_PATH)]
    try:
        frames.append(openmeteo.fetch(first - timedelta(days=1), last, lat, lon))
    # The live forecast below still covers today.
    except Exception as e:  # noqa: BLE001
        log(f"historical forecast for the capture days failed: {e}")
    frames.append(live.forecast_weather())
    cols = frames[0].columns
    return pl.concat([f.select(cols) for f in frames]).unique("time_utc", keep="first")


def calibrated_persistence(df: pl.DataFrame, train: pl.Series) -> pl.Series:
    """P(y | station, state now), fitted on the train rows. Fallback: the rate per
    state."""
    fit = df.filter(train)
    st = fit.group_by("sid", "full_now").agg(p=pl.col("y").mean(), n=pl.len())
    glob = fit.group_by("full_now").agg(g=pl.col("y").mean())
    out = (
        df.select("sid", "full_now")
        .join(st, on=["sid", "full_now"], how="left")
        .join(glob, on="full_now", how="left")
    )
    return out.select(
        pl.when(pl.col("n") >= 20).then(pl.col("p")).otherwise(pl.col("g"))
    ).to_series()


def run_horizon(con, h: int, target: str, months: list[str]) -> dict:
    log(f"h={h}: examples (±{TOLERANCE_MIN} min) and short features")
    targets.build_examples(con, h, tolerance_min=TOLERANCE_MIN)
    con.execute(f"DELETE FROM ex_{h} WHERE t < {OWN_T0}")
    feat = model_matrix.build(
        con,
        h,
        source=f"ex_{h}",
        lags=LAGS,
        lag_window="centered",
        lag_tolerance_min=TOLERANCE_MIN,
        out=f"feat_short_{h}",
    )
    con.execute(
        f"CREATE OR REPLACE TABLE stack_{h} AS "
        f"SELECT f.*, b.p_base FROM {feat} f JOIN base b USING (sid, t)"
    )
    X, y, meta = lgbm.matrix(
        con, f"stack_{h}", tuple(months), extra=["t", "full_now", "p_base"], features=FEATURES
    )
    day = meta["t"].dt.convert_time_zone(config.LOCAL_TZ.key).dt.date().cast(pl.String)
    parts, by_day = split(day.unique().to_list())
    part = day.replace_strict(parts, default="train")
    if not by_day:
        # Too few days: split by time. This only tests the code.
        t = meta["t"]
        cut1, cut2 = t.quantile(SPLIT[0]), t.quantile(SPLIT[1])
        part = pl.select(
            pl.when(t < cut1)
            .then(pl.lit("train"))
            .when(t < cut2)
            .then(pl.lit("fit"))
            .otherwise(pl.lit("report"))
        ).to_series()
    tr, fit, rep = (
        (part == "train").to_numpy(),
        (part == "fit").to_numpy(),
        (part == "report").to_numpy(),
    )
    if not (tr.any() and fit.any() and rep.any()):
        raise SystemExit(
            f"h={h}: not enough captured data to split "
            f"({tr.sum()} / {fit.sum()} / {rep.sum()} rows)"
        )
    log(
        f"h={h}: training on {tr.sum():,} rows, early stopping on {fit.sum():,}, "
        f"report {rep.sum():,}"
    )
    model = lgbm.train(X[tr], y[tr], X[fit], y[fit], features=FEATURES)
    df = meta.with_columns(
        p_short=pl.Series(model.predict(X)),
        p_persist_cal=calibrated_persistence(meta, pl.Series(tr)),
        p_planner=planner_heuristic(pl.col("full_now").cast(pl.Float64), pl.col("p_base"), h),
        day=day,
    )
    report = df.filter(pl.Series(rep))
    rep_days = report["day"].unique().to_list()
    weekdays = sum(np.datetime64(d).astype(object).weekday() < 5 for d in rep_days)
    out = {
        "h": h,
        "target": target,
        "by_day": by_day,
        "rows": report.height,
        "days": sorted(rep_days),
        "weekdays": weekdays,
    }
    out["dry_run"] = not by_day or weekdays < MIN_REPORT_WEEKDAYS
    rows = []
    for seg, frame in (("all", report), ("peak", report.filter(is_peak()))):
        if frame.is_empty():
            continue
        s = metrics.summarize(frame, MODELS)
        best = s.filter(pl.col("model") != "p_short").sort("brier").row(0, named=True)
        s = s.with_columns(
            segment=pl.lit(seg),
            reference=pl.lit(best["model"]),
            bss=1 - pl.col("brier") / best["brier"],
        )
        ci = (None, None)
        if by_day and len(rep_days) >= 3:
            ids = bootstrap.block_ids(frame, "day")
            ci = bootstrap.interval(
                bootstrap.brier_skill(frame, ["p_short"], best["model"], ids, N_BOOT)[:, 0]
            )
        rel = metrics.reliability(frame, "p_short").with_columns(
            gap=(pl.col("observed") - pl.col("predicted")).abs()
        )
        big = rel.filter(pl.col("n") >= MIN_BIN_N)
        rows.append(
            {"segment": seg, "table": s, "ci": ci, "gap": big["gap"].max() if big.height else None}
        )
    out["segments"] = rows
    out["importance"] = lgbm.importance(model, top=10)
    out["model"] = model
    return out


def render(results: list[dict]) -> str:
    lines = []
    for r in results:
        goal = "sin bicis" if r["target"] == "empty" else "sin anclajes"
        head = f"## {r['h']} min, objetivo: {goal}"
        lines.append(head + ("  ·  **DRY RUN: no es evidencia**" if r["dry_run"] else ""))
        split_text = "por día" if r["by_day"] else "por hora (muy pocos días)"
        lines.append(
            f"\nReporte: {r['rows']:,} filas, días {', '.join(r['days'])} "
            f"({r['weekdays']} entre semana), división {split_text}.\n"
        )
        lines.append("| Segmento | Modelo | Brier | Log loss | BSS | IC 95 % (días) |")
        lines.append("|---|---|---|---|---|---|")
        for seg in r["segments"]:
            for row in seg["table"].iter_rows(named=True):
                ref = " (ref)" if row["model"] == row["reference"] else ""
                ci = seg["ci"]
                band = (
                    f"[{ci[0]:+.3f}, {ci[1]:+.3f}]"
                    if row["model"] == "p_short" and ci[0] is not None
                    else ""
                )
                lines.append(
                    f"| {seg['segment']} | {row['model']}{ref} | {row['brier']:.4f} "
                    f"| {row['log_loss']:.4f} | {row['bss']:+.3f} | {band} |"
                )
            gap = seg["gap"]
            lines.append(
                f"| {seg['segment']} | brecha de calibración de p_short "
                f"| {'—' if gap is None else f'{gap:.3f}'} | | | |"
            )
        lines.append(
            "\nImportancia: " + ", ".join(f"{f} {g:.1%}" for f, g in r["importance"]) + "\n"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", choices=list(targets.TARGETS), default="empty")
    parser.add_argument("--horizons", type=int, nargs="+", default=[5, 10])
    parser.add_argument("--own", type=Path, default=capture_snapshots.DEFAULT_OUT)
    parser.add_argument("--raw", type=Path, default=Path("raw"))
    parser.add_argument("--artifacts", type=Path, help="default: artifacts/short/<target>/")
    args = parser.parse_args(argv)

    own = sorted(args.own.glob("*.parquet"))
    if not own:
        raise SystemExit(
            f"no capture snapshots in {args.own}: run ecobici.ingest.capture_snapshots"
        )
    files = live.model_files()
    con = duckdb.connect(config={"memory_limit": "10GB", "temp_directory": "data/duckdb_tmp"})
    log(f"loading {len(own)} capture days and the M6 history (station list and profiles)")
    targets.load_snapshots(con, [*files, *own], target=args.target)
    # Keep the capture start in SQL: a tz-aware value in Python needs pytz.
    con.execute(
        "CREATE OR REPLACE TABLE own_start AS SELECT min(t) AS t0 FROM snap WHERE file_month = ''"
    )
    days = [
        str(d)
        for (d,) in con.execute(
            f"SELECT DISTINCT CAST(t AS DATE)::VARCHAR FROM snap WHERE t >= {OWN_T0} ORDER BY 1"
        ).fetchall()
    ]
    months = [
        m for (m,) in con.execute(f"SELECT DISTINCT month FROM snap WHERE t >= {OWN_T0}").fetchall()
    ]
    model_matrix.prepare_shared(
        con,
        trip_flow(trip_ingest.DEFAULT_DIR, args.raw),
        weather_for(days),
        station_files=live.MODEL_FILES,
    )

    log(f"base: the {BASE_H}-min {args.target} model on every capture reading")
    frozen = live.load_frozen(BASE_ARTIFACTS[args.target], (BASE_H,))[BASE_H]
    saturated = live.saturated_by_horizon(files, (BASE_H,), target=args.target)[BASE_H]
    con.execute(
        f"CREATE OR REPLACE TABLE base_src AS SELECT {targets.example_cols(BASE_H)}, "
        f"NULL::BOOLEAN AS y FROM snap now WHERE now.ok AND now.t >= {OWN_T0}",
    )
    featb = model_matrix.build(con, BASE_H, source="base_src", out="feat_base")
    Xb, _, mb = lgbm.matrix(con, featb, tuple(months), extra=["t"])
    _, p_base = frozen.predict(Xb, mb.select(is_saturated_peak(saturated)).to_series().to_numpy())
    con.register("base_df", mb.select("sid", "t").with_columns(p_base=pl.Series(p_base)).to_arrow())
    con.execute("CREATE OR REPLACE TABLE base AS SELECT * FROM base_df")

    results = [run_horizon(con, h, args.target, months) for h in args.horizons]
    print(render(results))
    out = args.artifacts or Path("artifacts/short") / args.target
    for r in results:
        if r["dry_run"]:
            log(f"h={r['h']}: dry run, nothing saved")
        else:
            r["model"].save(out, r["h"])
            log(f"h={r['h']}: saved to {out}")
    return 0


if __name__ == "__main__":
    np.seterr(all="ignore")
    sys.exit(main())
