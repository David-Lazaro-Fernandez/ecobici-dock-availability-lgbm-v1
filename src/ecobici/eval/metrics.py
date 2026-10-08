"""Probability metrics for "station full at arrival" (PRD success metrics)."""

import math

import polars as pl

EPS = 1e-6


def brier(p: pl.Expr, y: pl.Expr) -> pl.Expr:
    return ((p - y.cast(pl.Float64)) ** 2).mean()


def log_loss(p: pl.Expr, y: pl.Expr) -> pl.Expr:
    q = p.clip(EPS, 1 - EPS)
    yf = y.cast(pl.Float64)
    return -(yf * q.log() + (1 - yf) * (1 - q).log()).mean()


def skill(score: float, reference: float) -> float:
    """Brier skill score: 1 − score / reference. >0 beats the reference."""
    return 1 - score / reference if reference > 0 else math.nan


def summarize(df: pl.DataFrame, models: list[str], y: str = "y") -> pl.DataFrame:
    """One row per model: n, base rate, Brier and log loss."""
    rows = []
    for m in models:
        r = df.select(
            n=pl.len(),
            base_rate=pl.col(y).cast(pl.Float64).mean(),
            brier=brier(pl.col(m), pl.col(y)),
            log_loss=log_loss(pl.col(m), pl.col(y)),
        ).row(0, named=True)
        rows.append({"model": m, **r})
    return pl.DataFrame(rows)


def reliability(df: pl.DataFrame, model: str, y: str = "y", bins: int = 10) -> pl.DataFrame:
    """Calibration table: mean predicted vs observed rate per probability bin."""
    return (
        df.select(
            bin=(pl.col(model) * bins).floor().clip(0, bins - 1).cast(pl.Int32),
            p=pl.col(model),
            y=pl.col(y).cast(pl.Float64),
        )
        .group_by("bin")
        .agg(n=pl.len(), predicted=pl.col("p").mean(), observed=pl.col("y").mean())
        .sort("bin")
    )
