from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl

from ecobici.eval import bootstrap


def frame(n_days=40, n_stations=20, per_block=10, day_shock=0.0, seed=0):
    """Rows per station × day; ``day_shock`` moves every station's rate on the same day."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_days):
        shock = rng.normal(0, day_shock)
        for s in range(n_stations):
            t0 = datetime(2025, 10, 1, 14, tzinfo=UTC) + timedelta(days=d)
            for i in range(per_block):
                rows.append((f"S{s}", t0 + timedelta(minutes=15 * i), shock))
    df = pl.DataFrame(rows, schema=["sid", "t", "shock"], orient="row")
    rate = (0.3 + df["shock"]).clip(0.01, 0.99).to_numpy()
    y = rng.random(df.height) < rate
    return df.with_columns(
        y=pl.Series(y),
        # Informative.
        good=pl.Series(np.where(y, 0.8, 0.2)),
        flat=pl.lit(0.3),
    )


def test_block_ids_by_local_day_and_station_day():
    df = frame(n_days=3, n_stations=2, per_block=2)
    assert bootstrap.block_ids(df, "day").max() + 1 == 3
    assert bootstrap.block_ids(df, "station_day").max() + 1 == 6
    # 23:30 and 00:30 local fall on different local days even within one UTC date.
    late = pl.DataFrame(
        {
            "sid": ["A", "A"],
            "t": [
                datetime(2025, 10, 2, 5, 30, tzinfo=UTC),
                datetime(2025, 10, 2, 6, 30, tzinfo=UTC),
            ],
        }
    )
    assert bootstrap.block_ids(late, "day").tolist() == [0, 1]


def test_brier_skill_interval_covers_point_and_is_zero_against_itself():
    df = frame()
    ids = bootstrap.block_ids(df, "station_day")
    bss = bootstrap.brier_skill(df, ["good", "flat"], "flat", ids, n_boot=200)
    assert bss.shape == (200, 2)
    assert np.allclose(bss[:, 1], 0)
    y = df["y"].cast(pl.Float64)
    point = 1 - ((df["good"] - y) ** 2).sum() / ((df["flat"] - y) ** 2).sum()
    lo, hi = bootstrap.interval(bss[:, 0])
    assert lo < point < hi and lo > 0


def test_day_blocks_widen_the_interval_under_system_wide_shocks():
    df = frame(day_shock=0.15)
    widths = {}
    for by in bootstrap.BLOCKS:
        bss = bootstrap.brier_skill(df, ["flat"], "good", bootstrap.block_ids(df, by), 300)
        lo, hi = bootstrap.interval(bss[:, 0])
        widths[by] = hi - lo
    assert widths["day"] > 1.5 * widths["station_day"]


def test_calibration_gap_small_when_calibrated_and_reproducible():
    rng = np.random.default_rng(3)
    n = 60_000
    p = rng.random(n)
    df = pl.DataFrame(
        {
            "sid": rng.integers(0, 50, n).astype(str),
            "t": [
                datetime(2025, 10, 1, tzinfo=UTC) + timedelta(days=int(d))
                for d in rng.integers(0, 30, n)
            ],
            "p": p,
            "y": rng.random(n) < p,
        }
    )
    ids = bootstrap.block_ids(df, "station_day")
    a, obs, pred = bootstrap.calibration_gap(df, "p", ids, min_bin_n=1000, n_boot=100)
    b, _, _ = bootstrap.calibration_gap(df, "p", ids, min_bin_n=1000, n_boot=100)
    assert np.array_equal(a, b)
    assert a.max() < 0.05
    assert obs.shape == pred.shape == (100, 10)
    # Bins under min_bin_n leave the max (gap 0) but keep their rates.
    gaps, obs_small, _ = bootstrap.calibration_gap(df, "p", ids, min_bin_n=10**6, n_boot=10)
    assert (gaps == 0).all() and not np.isnan(obs_small).any()
