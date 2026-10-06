"""M5: score the baselines on the validation months; test months are never loaded.

    uv run python -m ecobici.eval.baseline_report

Segments, all on validation:
- all: every example;
- peak: weekday arrivals 08:30–10:30;
- saturated: stations full >= 10% of weekday peak arrivals *in train* (M3's ~100);
- saturated_peak: both. This is where the product earns its keep.
"""

import argparse
import sys
from pathlib import Path

import duckdb
import polars as pl

from ecobici.eval import metrics
from ecobici.eval.splits import TRAIN, VALIDATION
from ecobici.features import targets
from ecobici.ingest import maxhalford
from ecobici.models import baselines

HORIZONS = (15, 30, 45)
MODELS = ["p_persist", "p_persist_cal", "p_hist"]
PEAK_SLOTS = (34, 41)  # 08:30–10:30 arrivals
SATURATED_MIN_RATE = 0.10


def saturated_stations(con: duckdb.DuckDBPyConnection, horizon_min: int) -> list[str]:
    rows = con.execute(
        f"""
        SELECT sid FROM train_{horizon_min}
        WHERE NOT weekend AND target_slot BETWEEN ? AND ?
        GROUP BY sid HAVING avg(y::int) >= ?
        """,
        [*PEAK_SLOTS, SATURATED_MIN_RATE],
    ).fetchall()
    return [r[0] for r in rows]


def validation_frame(con: duckdb.DuckDBPyConnection, pred: str) -> pl.DataFrame:
    cols = "sid, y, full_now, target_slot, weekend, " + ", ".join(MODELS)
    return pl.from_arrow(
        con.execute(
            f"SELECT {cols} FROM {pred} WHERE month IN (SELECT unnest(?))", [list(VALIDATION)]
        ).arrow()
    )


def segments(df: pl.DataFrame, saturated: list[str]) -> dict[str, pl.DataFrame]:
    peak = (~pl.col("weekend")) & pl.col("target_slot").is_between(*PEAK_SLOTS)
    sat = pl.col("sid").is_in(saturated)
    return {
        "all": df,
        "peak": df.filter(peak),
        "saturated": df.filter(sat),
        "saturated_peak": df.filter(peak & sat),
    }


def evaluate(con: duckdb.DuckDBPyConnection, horizon_min: int) -> tuple[pl.DataFrame, dict]:
    targets.build_examples(con, horizon_min)
    pred = baselines.predict(con, horizon_min)
    saturated = saturated_stations(con, horizon_min)
    val = validation_frame(con, pred)
    rows = []
    for name, seg in segments(val, saturated).items():
        s = metrics.summarize(seg, MODELS)
        rows.append(s.with_columns(segment=pl.lit(name), horizon=pl.lit(horizon_min)))
    best = segments(val, saturated)["saturated_peak"]
    rel = {m: metrics.reliability(best, m) for m in ("p_persist_cal", "p_hist")}
    return pl.concat(rows), {"saturated": len(saturated), "reliability": rel}


def to_markdown(table: pl.DataFrame) -> str:
    head = "| Horizon | Segment | n | Base rate | Model | Brier | Log loss |"
    lines = [head, "|---|---|---|---|---|---|---|"]
    for r in table.iter_rows(named=True):
        lines.append(
            f"| {r['horizon']} min | {r['segment']} | {r['n']:,} | {r['base_rate']:.3f} | "
            f"{r['model']} | {r['brier']:.4f} | {r['log_loss']:.4f} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=maxhalford.DEFAULT_DIR)
    args = parser.parse_args(argv)

    months = [*TRAIN, *VALIDATION]  # test months stay unread
    files = [args.dir / f"{m}.parquet" for m in months if (args.dir / f"{m}.parquet").exists()]
    con = duckdb.connect()
    targets.load_snapshots(con, files)

    tables = []
    for h in HORIZONS:
        table, extra = evaluate(con, h)
        tables.append(table)
        print(f"h={h}: {extra['saturated']} saturated stations (train)", file=sys.stderr)
        if h == 30:
            for m, rel in extra["reliability"].items():
                print(f"\n### Calibration, {m}, 30 min, saturated_peak\n")
                print("| Bin | n | Predicted | Observed |\n|---|---|---|---|")
                for r in rel.iter_rows(named=True):
                    print(
                        f"| {r['bin']} | {r['n']:,} | {r['predicted']:.3f} | {r['observed']:.3f} |"
                    )
    print("\n" + to_markdown(pl.concat(tables)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
