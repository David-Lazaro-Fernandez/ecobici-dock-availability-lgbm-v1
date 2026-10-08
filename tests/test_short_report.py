import polars as pl
import pytest

from ecobici.eval import short_report as sr


def test_split_by_day_in_order_with_the_dev_day_only_training():
    # Dev + 10 days.
    days = ["2026-10-06", *[f"2026-10-{d:02d}" for d in range(7, 17)]]
    parts, by_day = sr.split(days)
    assert by_day
    assert parts["2026-10-06"] == "train"
    order = [parts[d] for d in sorted(days) if d != "2026-10-06"]
    assert order == ["train"] * 6 + ["fit"] * 2 + ["report"] * 2


def test_split_with_too_few_days_is_not_by_day():
    parts, by_day = sr.split(["2026-10-06", "2026-10-07", "2026-10-08"])
    assert not by_day and set(parts.values()) == {"train"}


def test_planner_heuristic_is_linear_from_the_state_now():
    got = pl.select(
        # Not empty now.
        a=sr.planner_heuristic(pl.lit(0.0), pl.lit(0.6), 5),
        # Empty now.
        b=sr.planner_heuristic(pl.lit(1.0), pl.lit(0.6), 5),
        # Past 15 min: the base.
        c=sr.planner_heuristic(pl.lit(0.0), pl.lit(0.6), 30),
    ).row(0)
    assert got == pytest.approx((0.2, 1 - 0.4 / 3, 0.6))
