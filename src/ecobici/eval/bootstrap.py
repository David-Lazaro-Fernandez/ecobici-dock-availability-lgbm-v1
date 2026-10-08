"""Block bootstrap for the M6 metrics: confidence intervals for BSS and calibration gap.

Rows from the same station and day are correlated (one station stays full for an hour;
one rainy day moves the whole system), so whole blocks are resampled, never rows.
Two block definitions:

- ``day``: every row of one local day. Keeps system-wide shocks (weather, holidays,
  events) inside a block. Fewer blocks, wider and more honest intervals.
- ``station_day``: one station on one day. Many more blocks, narrower intervals;
  assumes stations are independent within a day.

Each replicate draws as many blocks as there are, with replacement, as multinomial
counts; every metric is then a weighted sum of per-block sums, so a replicate costs a
matrix product instead of a pass over millions of rows.
"""

import numpy as np
import polars as pl

from ecobici import config

BLOCKS = ("day", "station_day")


def block_ids(df: pl.DataFrame, by: str) -> np.ndarray:
    """Dense block index per row. ``df`` needs ``t`` (tz-aware) and, for station_day, sid."""
    day = pl.col("t").dt.convert_time_zone(config.LOCAL_TZ.key).dt.date().cast(pl.String)
    key = {"day": day, "station_day": pl.concat_str([pl.col("sid"), day], separator="|")}[by]
    return df.select(key.rank("dense").cast(pl.Int64) - 1).to_series().to_numpy()


def weights(n_blocks: int, n_boot: int, seed: int, chunk: int = 100):
    """Yield (chunk × n_blocks) arrays of resampling counts, ``n_boot`` rows in total."""
    rng = np.random.default_rng(seed)
    p = np.full(n_blocks, 1 / n_blocks)
    for start in range(0, n_boot, chunk):
        yield rng.multinomial(n_blocks, p, size=min(chunk, n_boot - start)).astype(np.float64)


def _sums(blocks: np.ndarray, n_blocks: int, values: np.ndarray) -> np.ndarray:
    return np.bincount(blocks, weights=values, minlength=n_blocks)


def brier_skill(
    df: pl.DataFrame,
    models: list[str],
    reference: str,
    blocks: np.ndarray,
    n_boot: int = 1000,
    seed: int = 0,
) -> np.ndarray:
    """(n_boot × len(models)) BSS of each model against ``reference`` per replicate.

    The reference stays fixed (chosen on the full sample); the rows are shared, so
    BSS = 1 − SSE_model / SSE_reference.
    """
    k = int(blocks.max()) + 1
    y = df["y"].cast(pl.Float64).to_numpy()
    sse = np.column_stack(
        [_sums(blocks, k, (df[m].to_numpy() - y) ** 2) for m in [*models, reference]]
    )
    out = [w @ sse for w in weights(k, n_boot, seed)]
    s = np.vstack(out)
    return 1 - s[:, :-1] / s[:, -1:]


def calibration_gap(
    df: pl.DataFrame,
    model: str,
    blocks: np.ndarray,
    min_bin_n: int,
    bins: int = 10,
    n_boot: int = 1000,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per replicate: max |observed − predicted| over bins with n >= ``min_bin_n``
    (n_boot,), and the per-bin observed and predicted rates (n_boot × bins).

    Bins are fixed by the prediction, as in ``metrics.reliability``. A bin below
    ``min_bin_n`` in a replicate is left out of that replicate's max; its rates are
    still returned (NaN only when the replicate drew no row in that bin).
    """
    k = int(blocks.max()) + 1
    p = df[model].to_numpy()
    y = df["y"].cast(pl.Float64).to_numpy()
    b = np.clip(np.floor(p * bins), 0, bins - 1).astype(np.int64)
    cell = blocks * bins + b
    shape = (k, bins)
    n = np.bincount(cell, minlength=k * bins).reshape(shape).astype(np.float64)
    sp = np.bincount(cell, weights=p, minlength=k * bins).reshape(shape)
    sy = np.bincount(cell, weights=y, minlength=k * bins).reshape(shape)
    gaps, obs, pred = [], [], []
    for w in weights(k, n_boot, seed):
        N, P, Y = w @ n, w @ sp, w @ sy
        with np.errstate(invalid="ignore", divide="ignore"):
            o, q = Y / N, P / N
        big_gap = np.where(N >= min_bin_n, np.abs(o - q), np.nan)
        gaps.append(np.nanmax(big_gap, axis=1, initial=0.0))
        obs.append(o)
        pred.append(q)
    return np.concatenate(gaps), np.vstack(obs), np.vstack(pred)


def interval(samples: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    """Percentile interval, ignoring NaN."""
    a = (1 - level) / 2
    lo, hi = np.nanquantile(samples, [a, 1 - a], axis=0)
    return lo, hi
