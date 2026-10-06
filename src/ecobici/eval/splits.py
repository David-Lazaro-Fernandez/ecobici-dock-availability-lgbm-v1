"""Temporal split for MaxHalford history (docs/reports/M2_history.md).

Never shuffled. Test months stay untouched until the final evaluation (M6/M7).
2025-07 and 2026-02..08 are excluded everywhere: the scraper degraded.
"""

TRAIN = tuple(f"{y}-{m:02d}" for y, m in [(2024, 9), (2024, 10), (2024, 11), (2024, 12)]) + tuple(
    f"2025-{m:02d}" for m in range(1, 7)
)
VALIDATION = tuple(f"2025-{m:02d}" for m in range(8, 13))
TEST = ("2026-01", "2026-09")

SPLITS = {"train": TRAIN, "validation": VALIDATION, "test": TEST}


def split_of(month: str) -> str | None:
    for name, months in SPLITS.items():
        if month in months:
            return name
    return None
