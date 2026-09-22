"""Numerology ЧС / ЧМ from a birth date — Excel-compatible.

ЧС (G3 = birth date)::

    IF(G3=""; ""; IF(MOD(DAY(G3); 9)=0; 9; MOD(DAY(G3); 9)))

That is the digital root of the day of month (1–9).
Example: day 12 → 1+2=3; day 98 is only an illustration of the same
reduction (9+8=17 → 8), not a calendar day.

ЧМ::

    IF(G3=""; ""; IF(MOD(DAY+MONTH+SUBSTITUTE(TEXT(YEAR;"0000");"0";""); 9)=0;
                     9; MOD(...)))

Year zeros are stripped first (2026 → 226, 2000 → 2), then the three
integers are summed and reduced to 1–9. Digit-sum of the printed date
``12.34.5678`` → 36 → 9 is the same 1–9 reduction, not a different rule.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional


def remainder_1_to_9(value: int) -> int:
    """Excel ``IF(MOD(n;9)=0; 9; MOD(n;9))`` (also maps 0 → 9)."""
    remainder = int(value) % 9
    return 9 if remainder == 0 else remainder


def year_without_zeros(year: int) -> int:
    """``SUBSTITUTE(TEXT(YEAR;\"0000\");\"0\";\"\")`` coerced to a number (blank → 0).

    ``2000`` becomes ``2``, not empty: only the zero characters are removed.
    """
    digits = f"{int(year):04d}".replace("0", "")
    return int(digits) if digits else 0


def chs_from_birth(birth: Optional[date]) -> Optional[int]:
    if birth is None:
        return None
    return remainder_1_to_9(birth.day)


def chm_from_birth(birth: Optional[date]) -> Optional[int]:
    if birth is None:
        return None
    total = birth.day + birth.month + year_without_zeros(birth.year)
    return remainder_1_to_9(total)


def numerology_payload(birth: Optional[date]) -> dict[str, Any]:
    return {
        "birth_date": birth.isoformat() if birth else None,
        "chs": chs_from_birth(birth),
        "chm": chm_from_birth(birth),
    }
