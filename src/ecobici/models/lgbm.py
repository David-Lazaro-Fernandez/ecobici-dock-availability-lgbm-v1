"""M6: one LightGBM classifier per horizon for P(station full at t + h), plus an
isotonic calibrator fitted on held-out validation months, and a Platt recalibration
for the saturated_peak subgroup (static or rolling)."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import polars as pl
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from ecobici.features.model_matrix import CATEGORICAL, FEATURES

PARAMS = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 127,
    "min_data_in_leaf": 200,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "max_bin": 255,
    "max_cat_to_onehot": 4,
    "cat_smooth": 20,
    "verbosity": -1,
    "num_threads": os.cpu_count() or 4,
    "seed": 7,
    # Same data → same model: fixed histogram layout and thread-independent sums.
    "deterministic": True,
    "force_col_wise": True,
}
MAX_ROUNDS = 3000
EARLY_STOPPING = 100


def matrix(
    con: duckdb.DuckDBPyConnection, table: str, months: tuple[str, ...], extra: list[str] = ()
) -> tuple[np.ndarray, np.ndarray, pl.DataFrame]:
    """(X float32, y, metadata) for the given months. Booleans become 0/1. Metadata
    holds y plus sid, target_slot, weekend and any ``extra`` columns."""
    # Prefixed so features that are also metadata (target_slot, weekend) don't collide.
    feat_cols = [f"f__{f}" for f in FEATURES]
    feats = ", ".join(
        f"CAST({f} AS FLOAT) AS {c}" for f, c in zip(FEATURES, feat_cols, strict=True)
    )
    meta_cols = ", ".join(["sid", "target_slot", "weekend", *extra])
    df = con.execute(
        f"SELECT {feats}, y::TINYINT AS y, {meta_cols} FROM {table} "
        # A stable row order: DuckDB scans in parallel, and LightGBM's bagging samples
        # by row index, so an unordered result gives a different model every run.
        f"WHERE month IN (SELECT unnest(?)) ORDER BY sid, t",
        [list(months)],
    ).pl()
    X = df.select(feat_cols).to_numpy().astype(np.float32, copy=False)
    return X, df["y"].to_numpy(), df.drop(feat_cols)


@dataclass
class Model:
    booster: lgb.Booster
    calibrator: IsotonicRegression

    def predict_raw(self, X: np.ndarray) -> np.ndarray:
        return self.booster.predict(X, num_iteration=self.booster.best_iteration)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.calibrator.predict(self.predict_raw(X))

    def save(self, directory: Path, horizon_min: int) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.booster.save_model(directory / f"lgbm_{horizon_min}.txt")
        iso = {
            "x": self.calibrator.X_thresholds_.tolist(),
            "y": self.calibrator.y_thresholds_.tolist(),
        }
        (directory / f"isotonic_{horizon_min}.json").write_text(json.dumps(iso))


def train(
    X: np.ndarray, y: np.ndarray, X_fit: np.ndarray, y_fit: np.ndarray, params: dict = PARAMS
) -> Model:
    """Train on (X, y); early-stop and calibrate on the held-out (X_fit, y_fit)."""
    cat = [FEATURES.index(c) for c in CATEGORICAL]
    dtrain = lgb.Dataset(X, y, feature_name=FEATURES, categorical_feature=cat, free_raw_data=True)
    dval = lgb.Dataset(X_fit, y_fit, reference=dtrain)
    booster = lgb.train(
        params,
        dtrain,
        num_boost_round=MAX_ROUNDS,
        valid_sets=[dval],
        valid_names=["val_fit"],
        callbacks=[lgb.early_stopping(EARLY_STOPPING, verbose=False), lgb.log_evaluation(0)],
    )
    raw = booster.predict(X_fit, num_iteration=booster.best_iteration)
    return Model(booster, fit_isotonic(raw, y_fit))


def importance(model: Model, top: int = 15) -> list[tuple[str, float]]:
    """Share of total split gain per feature."""
    gain = model.booster.feature_importance(importance_type="gain")
    total = gain.sum() or 1.0
    ranked = sorted(zip(FEATURES, gain / total, strict=True), key=lambda kv: -kv[1])
    return ranked[:top]


def fit_isotonic(p: np.ndarray, y: np.ndarray) -> IsotonicRegression:
    return IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(p, y)


@dataclass
class Platt:
    """P = σ(a · logit(p) + b): two parameters, monotone, smooth. Used to recalibrate an
    already calibrated probability inside a small subgroup, where isotonic would
    overfit its many steps."""

    a: float
    b: float

    EPS = 1e-6

    @classmethod
    def logit(cls, p: np.ndarray) -> np.ndarray:
        q = np.clip(p, cls.EPS, 1 - cls.EPS)
        return np.log(q / (1 - q))

    @classmethod
    def fit(cls, p: np.ndarray, y: np.ndarray) -> "Platt":
        lr = LogisticRegression(C=np.inf).fit(cls.logit(p)[:, None], y)
        return cls(float(lr.coef_[0, 0]), float(lr.intercept_[0]))

    def predict(self, p: np.ndarray) -> np.ndarray:
        return 1 / (1 + np.exp(-(self.a * self.logit(p) + self.b)))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"a": self.a, "b": self.b}))


def rolling_recalibrate(
    times: pl.Series,
    raw: np.ndarray,
    y: np.ndarray,
    score_from,
    window_days: int = 28,
    step_days: int = 7,
    fit=fit_isotonic,
    min_rows: int = 1000,
    fallback=None,
) -> np.ndarray:
    """Recalibrate weekly on the trailing ``window_days`` of labelled predictions.

    Emulates the PRD's daily retraining at the cheapest level: the booster is fixed and
    only the calibration map is refitted. For each week starting at or after
    ``score_from``, ``fit(p, y)`` (anything with ``.predict``) sees rows strictly
    before that week (labels up to t + h are known by then because the week boundary
    trails by at least a day). A week whose window has fewer than ``min_rows`` rows
    uses ``fallback`` if given, else stays NaN. Rows before ``score_from`` are NaN.
    """
    t = times.to_numpy()
    out = np.full(len(raw), np.nan)
    week = np.datetime64(score_from)
    end = t.max()
    while week <= end:
        nxt = week + np.timedelta64(step_days, "D")
        window = (t >= week - np.timedelta64(window_days, "D")) & (
            t < week - np.timedelta64(1, "D")
        )
        score = (t >= week) & (t < nxt)
        if score.any():
            if window.sum() >= min_rows:
                out[score] = fit(raw[window], y[window]).predict(raw[score])
            elif fallback is not None:
                out[score] = fallback.predict(raw[score])
        week = nxt
    return out
