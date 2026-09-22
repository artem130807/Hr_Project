"""TDD: psychometric scoring for complex_work_profile."""
import pytest

from app.psychometrics.scoring import (
    list_instruments_meta,
    load_instrument,
    public_instrument_payload,
    score_complex_profile,
)


def _all_mid_answers(data):
    answers = {}
    for it in data["items"]:
        if it["module"] == "disc":
            answers[it["code"]] = {"most": "A", "least": "B"}
        elif it["module"] == "avp":
            answers[it["code"]] = 3
        else:
            answers[it["code"]] = "A"
    return answers


def test_instrument_loaded_with_128_items():
    data = load_instrument("complex_work_profile")
    assert data["id"] == "complex_work_profile"
    assert len(data["items"]) == 128
    assert sum(1 for it in data["items"] if it["module"] == "disc") == 24
    assert sum(1 for it in data["items"] if it["module"] == "avp") == 80
    assert sum(1 for it in data["items"] if it["module"] == "sjt") == 24


def test_alias_loads_new_instrument():
    data = load_instrument("complex_work_behavior_220")
    assert data["id"] == "complex_work_profile"


def test_public_payload_hides_scoring_keys():
    pub = public_instrument_payload("complex_work_profile")
    assert "categories" not in pub["items"][0]
    assert pub["presentation"]["block_order"] == ["avp", "sjt", "disc"]
    assert [it["module"] for it in pub["items"][:80]] == ["avp"] * 80
    assert [it["module"] for it in pub["items"][80:104]] == ["sjt"] * 24
    assert [it["module"] for it in pub["items"][104:]] == ["disc"] * 24
    avp = pub["items"][0]
    assert avp["module"] == "avp"
    assert "reverse" not in avp
    sjt = next(it for it in pub["items"] if it["module"] == "sjt")
    assert "priorities" not in sjt
    assert "scores" not in sjt
    disc = next(it for it in pub["items"] if it["module"] == "disc")
    assert disc["options"]["A"]


def test_public_copy_uses_safe_pilot_terminology():
    pub = public_instrument_payload("complex_work_profile")
    block_titles = " ".join(block["title"] for block in pub["presentation"]["blocks"])
    assert "внутренний пилотный поведенческий блок" in block_titles
    assert "внутренний SJT, пилотная версия" in block_titles

    data = load_instrument("complex_work_profile")
    display_names = [
        str(value)
        for section in (data.get("avp_aspects", []), data.get("avp_factors", []), data.get("paei", []))
        for row in section
        for key, value in row.items()
        if key == "name"
    ]
    display_copy = " ".join(display_names)
    for forbidden in (
        "Интеллект",
        "Открытость и интеллект",
        "Производитель результата",
        "Администратор",
        "Предприниматель",
        "Интегратор",
        "ведущий тип",
    ):
        assert forbidden.lower() not in {name.lower() for name in display_names}
    assert "Интеллектуальная вовлечённость" in display_copy


def test_list_instruments_meta():
    meta = list_instruments_meta()
    assert any(m["id"] == "complex_work_profile" for m in meta)


def test_avp_reverse_and_mid_index():
    data = load_instrument("complex_work_profile")
    answers = _all_mid_answers(data)
    result = score_complex_profile(answers, data)
    for aspect in result["avp"]["aspects"]:
        assert aspect["score"] == pytest.approx(50.0, abs=0.01)
    extra = next(f for f in result["avp"]["factors"] if f["code"] == "E")
    es = next(f for f in result["avp"]["factors"] if f["code"] == "ES")
    assert extra["score"] == pytest.approx(50.0, abs=0.01)
    assert es["score"] == pytest.approx(50.0, abs=0.01)


def test_disc_most_least_raw_range():
    data = load_instrument("complex_work_profile")
    answers = _all_mid_answers(data)
    result = score_complex_profile(answers, data)
    work = result["behavior_preferences"]["В работе"]
    assert all(row["raw"] is not None for row in work)
    assert all(-8 <= row["raw"] <= 8 for row in work)
    assert all(0 <= row["score"] <= 100 for row in work)


def test_sjt_quality_index():
    data = load_instrument("complex_work_profile")
    answers = _all_mid_answers(data)
    result = score_complex_profile(answers, data)
    assert result["sjt"]["max"] == 72
    assert result["sjt"]["quality_index"] is not None
    assert 0 <= result["sjt"]["quality_index"] <= 100
    assert abs(sum(p["score"] for p in result["management_focus_distribution"]) - 100) < 0.05
    assert "disc" not in result
    assert "paei" not in result
    assert "leading_disc" not in result["summary"]
    assert "leading_paei" not in result["summary"]


def test_missing_answers_insufficient():
    result = score_complex_profile({"AVP-001": 4})
    assert result["quality"]["status"] == "Недостаточно данных"
    assert result["summary"]["behavior_preference"] is None


def test_rapid_and_short_session_flags():
    data = load_instrument("complex_work_profile")
    answers = _all_mid_answers(data)
    result = score_complex_profile(
        answers,
        data,
        timing={
            "active_duration_sec": 60,
            "wall_duration_sec": 60,
            "latencies_ms": {it["code"]: 400 for it in data["items"]},
        },
    )
    assert result["quality"]["status"] == "Критическая проверка"
    assert result["quality"]["speed_flag"] == "Критическая проверка"


def test_submit_schema_accepts_mixed_answers():
    from datetime import date
    from app.schemas.v1.psych_tests import PsychResultSubmit

    body = PsychResultSubmit(
        instrument_id="complex_work_profile",
        full_name="A",
        position="B",
        taken_at=date(2026, 8, 21),
        birth_date=date(1990, 1, 1),
        answers={
            "DISC-01": {"most": "A", "least": "C"},
            "AVP-001": 4,
            "SJT-01": "B",
        },
    )
    assert body.answers["AVP-001"] == 4
    assert body.answers["DISC-01"]["most"] == "A"
    assert body.answers["SJT-01"] == "B"
