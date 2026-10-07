import json

import duckdb
import numpy as np
import polars as pl

from ecobici.features.model_matrix import FEATURES
from ecobici.models import lgbm


def synthetic(n, rng):
    """Full is likelier when few docks are free and it's 'peak'."""
    X = rng.normal(size=(n, len(FEATURES))).astype(np.float32)
    X[:, FEATURES.index("station")] = rng.integers(0, 5, n)
    docks = rng.integers(0, 10, n)
    X[:, FEATURES.index("docks_now")] = docks
    logit = 1.5 - 0.8 * docks + 1.0 * X[:, FEATURES.index("flow_net_window")]
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(np.int8)
    return X, y


def test_train_learns_signal_and_calibrates(tmp_path):
    rng = np.random.default_rng(0)
    X, y = synthetic(20_000, rng)
    Xf, yf = synthetic(5_000, rng)
    params = {**lgbm.PARAMS, "num_threads": 2, "num_leaves": 15}
    model = lgbm.train(X, y, Xf, yf, params)

    Xt, yt = synthetic(5_000, rng)
    p = model.predict(Xt)
    assert p.min() >= 0 and p.max() <= 1
    brier = np.mean((p - yt) ** 2)
    assert brier < 0.8 * np.mean((yt.mean() - yt) ** 2)  # beats the base rate
    top = dict(lgbm.importance(model, top=3))
    assert "docks_now" in top

    model.save(tmp_path, 30)
    assert (tmp_path / "lgbm_30.txt").exists() and (tmp_path / "isotonic_30.json").exists()


def test_matrix_reads_only_requested_months_and_keeps_y_in_meta():
    con = duckdb.connect()
    rows = {f: [1.0, 2.0, 3.0] for f in FEATURES}
    rows |= {
        "y": [True, False, True],
        "sid": ["C", "B", "A"],
        "t": [3, 2, 1],
        "target_slot": [37, 36, 36],
        "weekend": [False] * 3,
        "month": ["2025-03", "2025-10", "2025-03"],
        "p_hist": [0.1, 0.2, 0.3],
    }
    con.register("src", pl.DataFrame(rows).to_arrow())
    con.execute("CREATE TABLE feat AS SELECT * FROM src")
    X, y, meta = lgbm.matrix(con, "feat", ("2025-03",), extra=["p_hist"])
    assert X.shape == (2, len(FEATURES)) and X.dtype == np.float32
    assert y.tolist() == [1, 1]
    assert meta["sid"].to_list() == ["A", "C"]  # ordered by station, then time
    assert meta.columns == ["y", "sid", "target_slot", "weekend", "p_hist"]


def test_training_is_reproducible():
    rng = np.random.default_rng(1)
    X, y = synthetic(8_000, rng)
    Xf, yf = synthetic(2_000, rng)
    params = {**lgbm.PARAMS, "num_threads": 4, "num_leaves": 15}
    a = lgbm.train(X, y, Xf, yf, params).predict(Xf)
    b = lgbm.train(X, y, Xf, yf, params).predict(Xf)
    assert np.array_equal(a, b)


def test_rolling_recalibrate_uses_only_the_past_and_tracks_drift():
    # Raw score stays 0.5 but the true rate drops from 50% to 10% after week 4.
    days = np.arange(np.datetime64("2025-10-01"), np.datetime64("2025-12-10"))
    times = np.repeat(days, 500).astype("datetime64[us]")
    rng = np.random.default_rng(0)
    rate = np.where(times < np.datetime64("2025-10-29"), 0.5, 0.1)
    y = (rng.random(len(times)) < rate).astype(int)
    raw = np.full(len(times), 0.5)
    out = lgbm.rolling_recalibrate(pl.Series(times), raw, y, score_from=np.datetime64("2025-10-29"))
    assert np.isnan(out[times < np.datetime64("2025-10-29")]).all()
    first_week = (times >= np.datetime64("2025-10-29")) & (times < np.datetime64("2025-11-05"))
    mixed = (times >= np.datetime64("2025-11-19")) & (times < np.datetime64("2025-11-26"))
    late = times >= np.datetime64("2025-12-03")
    assert out[first_week].mean() > 0.45  # only saw the 50% era
    # Window [10-22, 11-18): 7 days at 50% and 20 at 10% → ≈ 0.20.
    assert abs(out[mixed].mean() - (7 * 0.5 + 20 * 0.1) / 27) < 0.02
    assert out[late].mean() < 0.12  # window is entirely in the 10% era


def test_platt_corrects_overconfidence_and_round_trips(tmp_path):
    # True probability is a squashed version of p: σ(0.6 · logit(p) − 0.4).
    rng = np.random.default_rng(0)
    p = rng.uniform(0.01, 0.99, 50_000)
    truth = 1 / (1 + np.exp(-(0.6 * lgbm.Platt.logit(p) - 0.4)))
    y = (rng.random(len(p)) < truth).astype(int)
    platt = lgbm.Platt.fit(p, y)
    assert abs(platt.a - 0.6) < 0.05 and abs(platt.b + 0.4) < 0.05
    q = platt.predict(p)
    assert np.all(np.diff(q[np.argsort(p)]) >= 0)  # monotone
    assert np.abs(q - truth).max() < 0.03

    platt.save(tmp_path / "platt.json")
    loaded = lgbm.Platt(**json.loads((tmp_path / "platt.json").read_text()))
    assert np.array_equal(loaded.predict(p), q)


def test_rolling_recalibrate_falls_back_when_the_window_is_short():
    # Two days of history, then a week to score: the window is below min_rows.
    days = np.arange(np.datetime64("2025-10-01"), np.datetime64("2025-10-17"))
    times = np.repeat(days, 100).astype("datetime64[us]")
    rng = np.random.default_rng(0)
    raw = rng.uniform(0.1, 0.9, len(times))
    y = (rng.random(len(times)) < raw).astype(int)
    fallback = lgbm.Platt(a=1.0, b=-1.0)
    out = lgbm.rolling_recalibrate(
        pl.Series(times),
        raw,
        y,
        score_from=np.datetime64("2025-10-03"),
        fit=lgbm.Platt.fit,
        min_rows=500,
        fallback=fallback,
    )
    week1 = (times >= np.datetime64("2025-10-03")) & (times < np.datetime64("2025-10-10"))
    week2 = times >= np.datetime64("2025-10-10")
    # Week 1 sees 10-01 only (the last day before the week is skipped): 100 rows.
    assert np.array_equal(out[week1], fallback.predict(raw[week1]))
    # Week 2 sees 10-01..10-08: 800 rows, so it fits its own map (≈ identity here).
    assert not np.allclose(out[week2], fallback.predict(raw[week2]))
    assert np.abs(out[week2] - raw[week2]).mean() < 0.05
