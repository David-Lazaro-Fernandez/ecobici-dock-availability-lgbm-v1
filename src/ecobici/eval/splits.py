"""Temporal split for MaxHalford history (docs/reports/M2_history.md).

Never shuffled. Test months stay untouched until the final evaluation (M6/M7).
2025-07 and 2026-02..08 are excluded everywhere: the scraper degraded.
"""

TRAIN = tuple(f"{y}-{m:02d}" for y, m in [(2024, 9), (2024, 10), (2024, 11), (2024, 12)]) + tuple(
    f"2025-{m:02d}" for m in range(1, 7)
)
VALIDATION = tuple(f"2025-{m:02d}" for m in range(8, 13))
TEST = ("2026-01", "2026-09")
# 2026-09 counts only from the scraper's recovery (M2, "2026-09 en detalle"): before
# 09-11 local it still has the 2026-02..08 degradation. Its 12-min cadence shifts the
# 15/30/45 targets by −3/−6/+3 min, so it is reported apart from 2026-01.
TEST_FROM = {"2026-09": "2026-09-11"}  # local date, inclusive

SPLITS = {"train": TRAIN, "validation": VALIDATION, "test": TEST}


def split_of(month: str) -> str | None:
    for name, months in SPLITS.items():
        if month in months:
            return name
    return None


# Validation is split so the reported numbers never see a choice made on them:
# early stopping and calibration use VAL_FIT; the M6 report scores VAL_REPORT.
VAL_FIT = ("2025-08", "2025-09")
VAL_REPORT = ("2025-10", "2025-11", "2025-12")
