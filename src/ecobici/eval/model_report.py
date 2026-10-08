"""M6: train LightGBM per horizon and score it against the baselines.

    uv run python -m ecobici.eval.model_report

Train on TRAIN, early-stop and calibrate on VAL_FIT, report on VAL_REPORT. Test months
are never read. Targets (M5, approved): BSS > 0 vs the best baseline in every segment;
BSS >= 0.10 at 30 min on saturated_peak; |observed − predicted| <= 0.05 in every
calibration bin with n >= 1,000 on saturated_peak.

The targets keep the pre-registered reference (baselines fitted on TRAIN). The model
also sees VAL_FIT, so the report adds a fair reference: the best of the baselines refit
on TRAIN + VAL_FIT (``_tvf``) or recalibrated on VAL_FIT (``_iso``). Every BSS and
calibration gap gets a 95 % block-bootstrap interval (eval/bootstrap.py).

Subgroup calibration (next_steps.md, step 3): the global isotonic map is fitted on all
rows, 97 % of them easy "not full" cases, and leaves saturated_peak over-predicted.
``p_lgbm_sub`` recalibrates only saturated_peak rows with a Platt map fitted on VAL_FIT;
``p_lgbm_sub_roll`` refits that map weekly on the trailing 28 days of saturated_peak
rows and falls back to the static map when the window is short. ``p_lgbm_sub_roll`` is
the model frozen for the test months (FROZEN); ``p_lgbm`` stays the pre-registered one.
"""

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import polars as pl
from sklearn.isotonic import IsotonicRegression

from ecobici import config
from ecobici.eval import bootstrap, metrics
from ecobici.eval.baseline_report import (
    HORIZONS,
    is_saturated_peak,
    saturated_stations,
    segments,
)
from ecobici.eval.splits import TRAIN, VAL_FIT, VAL_REPORT, VALIDATION
from ecobici.features import model_matrix, targets
from ecobici.features import trips as trip_features
from ecobici.ingest import maxhalford, openmeteo
from ecobici.ingest import trips as trip_ingest
from ecobici.models import baselines, lgbm

BASELINES = ["p_persist", "p_persist_cal", "p_hist"]
# Same data as the model: refit on TRAIN + VAL_FIT, or recalibrated on VAL_FIT.
REFIT = {"_tvf": (*TRAIN, *VAL_FIT)}
REFIT_BASELINES = [f"{b}{s}" for s in REFIT for b in baselines.FITTED]
ISO_BASELINES = [f"{b}_iso" for b in baselines.FITTED]
ALL_BASELINES = [*BASELINES, *REFIT_BASELINES, *ISO_BASELINES]
# p_lgbm is the pre-registered model (one calibration on VAL_FIT). p_lgbm_recal adds
# weekly rolling recalibration, chosen after seeing drift in M6; confirm it on test.
LGBM = ["p_lgbm_raw", "p_lgbm", "p_lgbm_recal", "p_lgbm_sub", "p_lgbm_sub_roll"]
MODELS = [*ALL_BASELINES, *LGBM]
PRIMARY = "p_lgbm"
# Chosen on 2026-10-06, after VAL_REPORT and before any test month.
FROZEN = "p_lgbm_sub_roll"
CHECKED = (PRIMARY, "p_lgbm_recal", "p_lgbm_sub", FROZEN)
# ~1.5 weeks of weekday peaks (~19 k saturated_peak rows a month). Shorter windows use
# the static VAL_FIT map.
SUB_MIN_ROWS = 5000
N_BOOT = 1000
# 2025-10-01 00:00 CDMX, in UTC.
REPORT_START = np.datetime64("2025-10-01T06:00")
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


@dataclass(frozen=True)
class Period:
    """A scored period, [start, end) in naive UTC. A period with ``report=False`` is
    only history for the rolling recalibrations (for example VAL_REPORT before a test
    month)."""

    name: str
    start: np.datetime64
    end: np.datetime64
    report: bool = True


VAL_PERIODS = (Period("VAL_REPORT", REPORT_START, np.datetime64("2026-01-01T06:00")),)


def fit_predict(
    con,
    h: int,
    artifacts: Path,
    periods: tuple[Period, ...] = VAL_PERIODS,
    lag_window: str = "trailing",
    expect: Path | None = None,
) -> tuple[dict[str, pl.DataFrame], list[str], dict]:
    """Train on TRAIN, calibrate on VAL_FIT, and score each period. Return one frame per
    reported period with all model columns, the saturated stations, and model info.

    ``expect``: a directory with the frozen artifacts. Before any score, the new
    artifacts must be byte-identical to them. If not, raise RuntimeError.
    """
    log(f"h={h}: examples + baselines")
    targets.build_examples(con, h)
    baselines.predict(con, h, refits=REFIT)
    saturated = saturated_stations(con, h)
    log(f"h={h}: features")
    feat = model_matrix.build(con, h, source=f"pred_{h}", lag_window=lag_window)
    present = con.execute(
        "SELECT "
        + ", ".join(f"avg((docks_lag{lag} IS NOT NULL)::int)" for lag in model_matrix.LAGS_MIN)
        + f" FROM {feat}"
    ).fetchone()
    present = dict(zip(model_matrix.LAGS_MIN, present, strict=True))
    shares = ", ".join(f"{lag} min {v:.1%}" for lag, v in present.items())
    log(f"h={h}: lags present ({lag_window}): {shares}")

    X, y, _ = lgbm.matrix(con, feat, TRAIN)
    Xf, yf, _ = lgbm.matrix(con, feat, VAL_FIT)
    log(f"h={h}: training on {len(y):,} rows, early stopping on {len(yf):,}")
    t0 = time.time()
    model = lgbm.train(X, y, Xf, yf)
    train_s = time.time() - t0
    del X, y, Xf, yf
    model.save(artifacts, h)

    # VAL_FIT rows are scored too, only as history for the rolling recalibrations.
    months = sorted({*VAL_FIT, *VAL_REPORT, *(m for p in periods for m in _months(p))})
    extra = [*BASELINES, *REFIT_BASELINES, "t", "month"]
    Xr, yr, meta = lgbm.matrix(con, feat, tuple(months), extra=extra)
    raw = model.predict_raw(Xr)
    del Xr
    times = meta["t"].dt.convert_time_zone("UTC").dt.replace_time_zone(None)
    t = times.to_numpy()
    in_fit = meta["month"].is_in(VAL_FIT).to_numpy()
    in_period = {p.name: (t >= p.start) & (t < p.end) for p in periods}
    # Rows outside VAL_FIT and the periods (for example 2026-09-01 to 10) are never history.
    usable = in_fit | np.logical_or.reduce(list(in_period.values()))
    p_global = model.calibrator.predict(raw)
    # The subgroup map applies after the global map, on saturated_peak rows only.
    sub = meta.select(is_saturated_peak(saturated)).to_series().to_numpy()
    static = lgbm.Platt.fit(p_global[sub & in_fit], yr[sub & in_fit])
    static.save(artifacts / f"platt_sub_{h}.json")
    if expect is not None:
        _check_frozen(artifacts, expect, h)

    def rolling(src: np.ndarray, mask: np.ndarray, period: Period, **kw) -> np.ndarray:
        """Weekly recalibration of ``src`` on the ``mask`` rows of ``period``. The history
        is the usable rows before the period."""
        rows = mask & usable & (t < period.end)
        out = np.full(len(raw), np.nan)
        out[rows] = lgbm.rolling_recalibrate(
            times.filter(pl.Series(rows)), src[rows], yr[rows], score_from=period.start, **kw
        )
        return out

    everywhere = np.ones(len(raw), dtype=bool)
    reports = {}
    for p in periods:
        if not p.report:
            continue
        here = in_period[p.name]
        # With too little history (the first week of 2026-09), use the VAL_FIT map.
        recal = rolling(raw, everywhere, p, fallback=model.calibrator)
        roll_sub = rolling(
            p_global, sub, p, fit=lgbm.Platt.fit, min_rows=SUB_MIN_ROWS, fallback=static
        )
        p_sub, p_sub_roll = p_global.copy(), p_global.copy()
        p_sub[sub] = static.predict(p_global[sub])
        p_sub_roll[sub] = roll_sub[sub]
        # The baselines get the calibration step of the model: isotonic on VAL_FIT.
        iso = {
            f"{b}_iso": IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            .fit(meta[b].to_numpy()[in_fit], yr[in_fit])
            .predict(meta[b].to_numpy())
            for b in baselines.FITTED
        }
        reports[p.name] = meta.with_columns(
            p_lgbm_raw=pl.Series(raw),
            p_lgbm=pl.Series(p_global),
            p_lgbm_recal=pl.Series(recal),
            p_lgbm_sub=pl.Series(p_sub),
            p_lgbm_sub_roll=pl.Series(p_sub_roll),
            **{k: pl.Series(v) for k, v in iso.items()},
        ).filter(pl.Series(here))
    for name in (f"ex_{h}", f"pred_{h}", f"feat_{h}", f"train_{h}"):
        con.execute(f"DROP TABLE IF EXISTS {name}")
    info = {
        "importance": lgbm.importance(model),
        "best_iteration": model.booster.best_iteration,
        "train_seconds": train_s,
        "lags_present": present,
    }
    return reports, saturated, info


def _months(p: Period) -> list[str]:
    """Local months touched by a period (CDMX is UTC−6 all year)."""
    lo = (p.start - np.timedelta64(6, "h")).astype("datetime64[M]")
    hi = (p.end - np.timedelta64(6, "h") - np.timedelta64(1, "s")).astype("datetime64[M]")
    return [str(m) for m in np.arange(lo, hi + np.timedelta64(1, "M"))]


def _check_frozen(fresh: Path, frozen: Path, h: int) -> None:
    for name in (f"lgbm_{h}.txt", f"isotonic_{h}.json", f"platt_sub_{h}.json"):
        if (fresh / name).read_bytes() != (frozen / name).read_bytes():
            raise RuntimeError(f"{name} differs from the frozen {frozen / name}")
    log(f"h={h}: model and calibrators match the frozen artifacts")


def evaluate(report: pl.DataFrame, saturated: list[str], center: set[str], h: int) -> dict:
    """Every metric, check and interval for one scored period."""
    log(f"h={h}: bootstrap")
    seg_rows, checks, ci = [], [], []
    for name, seg in segments(report, saturated).items():
        s = metrics.summarize(seg, MODELS)
        best = s.filter(pl.col("model").is_in(BASELINES)).sort("brier").row(0, named=True)
        fair = s.filter(pl.col("model").is_in(ALL_BASELINES)).sort("brier").row(0, named=True)
        s = s.with_columns(
            segment=pl.lit(name),
            horizon=pl.lit(h),
            reference=pl.lit(best["model"]),
            bss=1 - pl.col("brier") / best["brier"],
            fair_reference=pl.lit(fair["model"]),
            bss_fair=1 - pl.col("brier") / fair["brier"],
        )
        seg_rows.append(s)
        for block in bootstrap.BLOCKS:
            ids = bootstrap.block_ids(seg, block)
            for kind, ref in (("pre-registered", best), ("fair", fair)):
                bss = bootstrap.brier_skill(seg, [PRIMARY, FROZEN], ref["model"], ids, N_BOOT)
                for j, m in enumerate((PRIMARY, FROZEN)):
                    lo, hi = bootstrap.interval(bss[:, j])
                    point = s.filter(pl.col("model") == m)[
                        "bss" if kind == "pre-registered" else "bss_fair"
                    ].item()
                    ci.append(
                        {
                            "model": m,
                            "segment": name,
                            "block": block,
                            "reference": ref["model"],
                            "kind": kind,
                            "bss": point,
                            "lo": lo,
                            "hi": hi,
                            "blocks": int(ids.max()) + 1,
                        }
                    )
        for m in CHECKED:
            bss = s.filter(pl.col("model") == m)["bss"].item()
            checks.append((m, f"BSS > 0, {name}", bss, bss > 0))
            if name == "saturated_peak" and h == 30:
                ok = bss >= TARGET_BSS_PRODUCT
                checks.append((m, f"BSS >= {TARGET_BSS_PRODUCT}, saturated_peak", bss, ok))
    sat_peak = segments(report, saturated)["saturated_peak"]
    rel, gap_ci = {}, []
    for m in CHECKED:
        gap, rel[m] = calibration_gap(sat_peak, m)
        name = f"calibration gap <= {TARGET_CALIBRATION}, saturated_peak"
        checks.append((m, name, gap, gap <= TARGET_CALIBRATION))
        for block in bootstrap.BLOCKS:
            ids = bootstrap.block_ids(sat_peak, block)
            gaps, obs, _ = bootstrap.calibration_gap(sat_peak, m, ids, MIN_BIN_N, n_boot=N_BOOT)
            lo, hi = bootstrap.interval(gaps)
            gap_ci.append(
                {
                    "model": m,
                    "block": block,
                    "gap": gap,
                    "lo": lo,
                    "hi": hi,
                    "p_ok": float((gaps <= TARGET_CALIBRATION).mean()),
                }
            )
            # The wider interval goes on the reliability diagram.
            if block == "day":
                olo, ohi = bootstrap.interval(obs)
                rel[m] = rel[m].with_columns(
                    observed_lo=pl.Series(olo).gather(rel[m]["bin"]),
                    observed_hi=pl.Series(ohi).gather(rel[m]["bin"]),
                )

    is_center = pl.col("sid").is_in(list(center))
    v8 = {
        m: {
            "center": ece(report.filter(is_center), m),
            "periphery": ece(report.filter(~is_center), m),
        }
        for m in CHECKED
    }
    return {
        "horizon": h,
        "table": pl.concat(seg_rows),
        "checks": checks,
        "bss_ci": pl.DataFrame(ci),
        "gap_ci": pl.DataFrame(gap_ci),
        "reliability": {m: rel[m] for m in (PRIMARY, FROZEN)},
        "v8_ece": v8,
    }


def run_horizon(con, h: int, artifacts: Path, lag_window: str = "trailing") -> dict:
    reports, saturated, info = fit_predict(con, h, artifacts, lag_window=lag_window)
    return {**evaluate(reports["VAL_REPORT"], saturated, center_stations(con), h), **info}


def render(results: list[dict], title: str = "Resultados (validación, 2025-10 → 2025-12)") -> str:
    out = [f"## {title}\n"]
    out.append(
        "`(ref)`: mejor línea base fijada de antemano (ajustada con TRAIN). "
        "`(ref justa)`: mejor de todas, incluidas `_tvf` (TRAIN + VAL_FIT) e `_iso` "
        "(recalibrada en VAL_FIT).\n"
    )
    out.append(
        "| Horizon | Segment | n | Base rate | Model | Brier | Log loss "
        "| BSS (ref) | BSS (ref justa) |"
    )
    out.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        for row in r["table"].iter_rows(named=True):
            marks = [
                tag
                for tag, col in (("ref", "reference"), ("ref justa", "fair_reference"))
                if row["model"] == row[col]
            ]
            mark = f" ({', '.join(marks)})" if marks else ""
            out.append(
                f"| {row['horizon']} min | {row['segment']} | {row['n']:,} | "
                f"{row['base_rate']:.3f} | {row['model']}{mark} | {row['brier']:.4f} | "
                f"{row['log_loss']:.4f} | {row['bss']:+.3f} | {row['bss_fair']:+.3f} |"
            )
    out.append(
        f"\n## Intervalos de confianza (bootstrap por bloques, {N_BOOT} réplicas, IC 95 %)\n"
    )
    out.append(f"### BSS de {PRIMARY} y {FROZEN}\n")
    out.append("| Horizon | Segment | Modelo | Referencia | Bloque | Bloques | BSS | IC 95 % |")
    out.append("|---|---|---|---|---|---|---|---|")
    for r in results:
        for c in r["bss_ci"].iter_rows(named=True):
            out.append(
                f"| {r['horizon']} min | {c['segment']} | {c['model']} | "
                f"{c['reference']} ({c['kind']}) | "
                f"{c['block']} | {c['blocks']:,} | {c['bss']:+.3f} | "
                f"[{c['lo']:+.3f}, {c['hi']:+.3f}] |"
            )
    out.append(f"\n### Brecha de calibración en saturated_peak (meta ≤ {TARGET_CALIBRATION})\n")
    out.append(
        "La brecha es el máximo sobre los bins con n ≥ 1,000, así que el bootstrap la "
        "sesga hacia arriba: el IC es conservador.\n"
    )
    out.append("| Horizon | Modelo | Bloque | Brecha | IC 95 % | Réplicas ≤ meta |")
    out.append("|---|---|---|---|---|---|")
    for r in results:
        for c in r["gap_ci"].iter_rows(named=True):
            out.append(
                f"| {r['horizon']} min | {c['model']} | {c['block']} | {c['gap']:.3f} | "
                f"[{c['lo']:.3f}, {c['hi']:.3f}] | {c['p_ok']:.0%} |"
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
            out.append("| Bin | n | Predicted | Observed | IC 95 % (días) |\n|---|---|---|---|---|")
            for b in rel.iter_rows(named=True):
                band = (
                    f"[{b['observed_lo']:.3f}, {b['observed_hi']:.3f}]"
                    # NaN: bin too small.
                    if b["observed_lo"] == b["observed_lo"]
                    else "—"
                )
                out.append(
                    f"| {b['bin']} | {b['n']:,} | {b['predicted']:.3f} | "
                    f"{b['observed']:.3f} | {band} |"
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
        out.append(
            "\nRezagos presentes: "
            + ", ".join(f"{lag} min {v:.1%}" for lag, v in r["lags_present"].items())
        )
    return "\n".join(out)


def plot_reliability(results: list[dict], path: Path, period: str = "VAL_REPORT") -> None:
    """Reliability diagram of PRIMARY and FROZEN on saturated_peak, one panel per
    horizon, with the day-block 95 % interval of each bin's observed rate and the
    ±target band. Hollow markers: bins under MIN_BIN_N, which the target ignores."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, grid = "#0b0b0b", "#52514e", "#e4e3df"
    colors = {PRIMARY: "#2a78d6", FROZEN: "#eb6834"}
    fig, axes = plt.subplots(1, len(results), figsize=(4 * len(results), 4.6), squeeze=False)
    for ax, r in zip(axes[0], results, strict=True):
        d = np.linspace(0, 1, 2)
        ax.fill_between(d, d - TARGET_CALIBRATION, d + TARGET_CALIBRATION, color=grid, lw=0)
        ax.plot(d, d, color=muted, lw=1, ls="--")
        title = [f"{r['horizon']} min"]
        for m, series in colors.items():
            rel = r["reliability"][m]
            x, o = rel["predicted"].to_numpy(), rel["observed"].to_numpy()
            lo, hi = rel["observed_lo"].to_numpy(), rel["observed_hi"].to_numpy()
            ax.plot(x, o, color=series, lw=2, zorder=2, label=m)
            ax.vlines(x, lo, hi, color=series, lw=1.5, zorder=2)
            big = rel["n"].to_numpy() >= MIN_BIN_N
            for mask, face in ((big, series), (~big, "white")):
                ax.plot(x[mask], o[mask], "o", ms=8, mfc=face, mec=series, mew=2, zorder=3)
            gap = next(
                c
                for c in r["gap_ci"].iter_rows(named=True)
                if c["model"] == m and c["block"] == "day"
            )
            title.append(f"{m}: brecha {gap['gap']:.3f} [{gap['lo']:.3f}, {gap['hi']:.3f}]")
        ax.set_title("\n".join(title), color=ink, fontsize=9, loc="left")
        ax.set(xlim=(0, 1), ylim=(0, 1), aspect="equal")
        ax.set_xlabel("Probabilidad predicha", color=muted, fontsize=9)
        ax.tick_params(colors=muted, labelsize=8, length=0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(grid)
    axes[0][0].set_ylabel("Frecuencia observada de estación llena", color=muted, fontsize=9)
    axes[0][0].legend(loc="upper left", frameon=False, fontsize=8, labelcolor=ink)
    fig.suptitle(
        f"Calibración en saturadas + pico ({period}). "
        f"Banda gris: ±{TARGET_CALIBRATION}; barras: IC 95 % por días; "
        f"huecos: bins con n < {MIN_BIN_N:,}.",
        color=ink,
        fontsize=10,
        x=0.01,
        ha="left",
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=maxhalford.DEFAULT_DIR)
    parser.add_argument("--trips", type=Path, default=trip_ingest.DEFAULT_DIR)
    parser.add_argument("--weather", type=Path, default=openmeteo.DEFAULT_PATH)
    parser.add_argument("--raw", type=Path, default=Path("raw"))
    parser.add_argument(
        "--target",
        choices=list(targets.TARGETS),
        default="full",
        help="full: no free dock (the frozen M6 model); empty: no bike to take",
    )
    parser.add_argument("--artifacts", type=Path, help="default: artifacts/[empty/]")
    parser.add_argument("--horizons", type=int, nargs="+", default=list(HORIZONS))
    parser.add_argument("--duckdb-memory", default="10GB")
    parser.add_argument(
        "--lag-window",
        choices=model_matrix.LAG_WINDOWS,
        default="trailing",
        help="trailing is the frozen M6 model; centered is an experiment",
    )
    parser.add_argument("--figure", type=Path, help="default: M6_reliability[_empty].png")
    args = parser.parse_args(argv)
    empty = args.target == "empty"
    args.artifacts = args.artifacts or Path("artifacts/empty" if empty else "artifacts")
    figure = "M6_reliability_empty.png" if empty else "M6_reliability.png"
    args.figure = args.figure or Path("docs/reports/figures") / figure

    # Test months stay unread.
    months = [*TRAIN, *VALIDATION]
    files = [args.dir / f"{m}.parquet" for m in months if (args.dir / f"{m}.parquet").exists()]
    # Cap DuckDB and let it spill: by default it may take 80% of RAM, which starves
    # LightGBM and the rest of the machine.
    spill = Path("data/duckdb_tmp")
    spill.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(config={"memory_limit": args.duckdb_memory, "temp_directory": str(spill)})
    log("loading snapshots, flows, weather")
    targets.load_snapshots(con, files, target=args.target)
    model_matrix.prepare_shared(con, trip_flow(args.trips, args.raw), pl.read_parquet(args.weather))

    results = []
    for h in args.horizons:
        results.append(run_horizon(con, h, args.artifacts, args.lag_window))
        log(f"h={h}: done")
    title = "Resultados (validación, 2025-10 → 2025-12)"
    print(render(results, title=f"{title}, objetivo: sin bicis" if empty else title))
    plot_reliability(results, args.figure)
    frozen_ok = all(ok for r in results for m, _, _, ok in r["checks"] if m == FROZEN)
    return 0 if frozen_ok else 2


if __name__ == "__main__":
    np.seterr(all="ignore")
    sys.exit(main())
