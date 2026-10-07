import numpy as np
import polars as pl

from ecobici.eval import test_report as tr


def test_final_periods_follow_the_split():
    periods = {p.name: p for p in tr.final_periods()}
    assert not periods["VAL_REPORT"].report  # history for 2026-01's rolling windows
    jan, sep = periods["2026-01"], periods["2026-09"]
    # Local midnights (CDMX, UTC−6) as naive UTC.
    assert jan.start == np.datetime64("2026-01-01T06:00")
    assert jan.end == np.datetime64("2026-02-01T06:00")
    assert periods["VAL_REPORT"].end == jan.start
    assert sep.start == np.datetime64("2026-09-11T06:00")  # splits.TEST_FROM
    assert sep.end == np.datetime64("2026-10-01T06:00")


def test_fallback_share_counts_rows_scored_by_the_static_map():
    report = pl.DataFrame(
        {
            "sid": ["S"] * 4 + ["other"],
            "weekend": [False] * 5,
            "target_slot": [36] * 5,
            "p_lgbm_sub": [0.1, 0.2, 0.3, 0.4, 0.5],
            "p_lgbm_sub_roll": [0.1, 0.2, 0.35, 0.45, 0.5],
        }
    )
    assert tr.fallback_share(report, ["S"]) == 0.5  # "other" is not saturated
