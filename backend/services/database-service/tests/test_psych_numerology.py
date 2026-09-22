from datetime import date

from app.psychometrics.numerology import (
    chm_from_birth,
    chs_from_birth,
    numerology_payload,
    remainder_1_to_9,
    year_without_zeros,
)


def test_remainder_maps_multiples_of_nine_to_nine():
    assert remainder_1_to_9(0) == 9
    assert remainder_1_to_9(9) == 9
    assert remainder_1_to_9(18) == 9
    assert remainder_1_to_9(12) == 3
    assert remainder_1_to_9(17) == 8


def test_chs_is_digital_root_of_day():
    assert chs_from_birth(date(1998, 8, 12)) == 3
    assert chs_from_birth(date(1990, 1, 9)) == 9
    assert chs_from_birth(date(1990, 1, 18)) == 9
    assert chs_from_birth(date(1990, 1, 27)) == 9
    assert chs_from_birth(date(1990, 1, 10)) == 1
    assert chs_from_birth(None) is None


def test_year_without_zeros_matches_excel_substitute():
    assert year_without_zeros(2026) == 226
    assert year_without_zeros(2000) == 2
    assert year_without_zeros(2010) == 21
    assert year_without_zeros(1998) == 1998


def test_chm_day_plus_month_plus_stripped_year():
    # 12.08.1998 → 12+8+1998=2018 → 2
    assert chm_from_birth(date(1998, 8, 12)) == 2
    # 15.03.2000 → 15+3+2=20 → 2  (year "2000" without zeros → 2)
    assert chm_from_birth(date(2000, 3, 15)) == 2
    # All-digit illustration 12.03.4567 → 1+2+0+3+4+5+6+7 = 28 → 10 → 1
    # Formula: 12+3+4567=4582 → 4+5+8+2=19 → 10 → 1
    assert chm_from_birth(date(4567, 3, 12)) == 1
    assert chm_from_birth(None) is None


def test_numerology_payload():
    payload = numerology_payload(date(1998, 8, 12))
    assert payload == {"birth_date": "1998-08-12", "chs": 3, "chm": 2}
