"""Mexican public holidays (LFT art. 74) plus Holy Thursday/Friday, 2024–2026.

Holy week is not an official rest day but empties offices, which is what moves
dock demand. Listed explicitly rather than computed so the dates are auditable.
"""

from datetime import date

HOLIDAYS: frozenset[date] = frozenset(
    {
        # 2024
        date(2024, 1, 1), date(2024, 2, 5), date(2024, 3, 18), date(2024, 3, 28),
        date(2024, 3, 29), date(2024, 5, 1), date(2024, 9, 16), date(2024, 10, 1),
        date(2024, 11, 18), date(2024, 12, 25),
        # 2025
        date(2025, 1, 1), date(2025, 2, 3), date(2025, 3, 17), date(2025, 4, 17),
        date(2025, 4, 18), date(2025, 5, 1), date(2025, 9, 16), date(2025, 11, 17),
        date(2025, 12, 25),
        # 2026
        date(2026, 1, 1), date(2026, 2, 2), date(2026, 3, 16), date(2026, 4, 2),
        date(2026, 4, 3), date(2026, 5, 1), date(2026, 9, 16), date(2026, 11, 16),
        date(2026, 12, 25),
    }
)  # fmt: skip
