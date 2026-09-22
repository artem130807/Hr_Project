"""TDD: psych test result submit/list endpoints (unit-level)."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.endpoints.v1 import psych_tests as mod
from app.psychometrics.scoring import load_instrument
from app.schemas.v1.psych_tests import PsychResultRead, PsychResultSubmit


def _full_answers():
    data = load_instrument("complex_work_profile")
    answers = {}
    for it in data["items"]:
        if it["module"] == "disc":
            answers[it["code"]] = {"most": "A", "least": "B"}
        elif it["module"] == "avp":
            answers[it["code"]] = 3
        else:
            answers[it["code"]] = "A"
    return answers


@pytest.mark.asyncio
async def test_submit_scores_and_persists():
    body = PsychResultSubmit(
        instrument_id="complex_work_profile",
        full_name="Иванов Иван",
        position="Логист",
        taken_at=date(2026, 8, 14),
        birth_date=date(1998, 8, 12),
        answers=_full_answers(),
    )
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    async def _refresh(row):
        row.id = 7
        row.created_at = None
        row.updated_at = None

    db.refresh = AsyncMock(side_effect=_refresh)

    row = await mod.submit_psych_result(body, db)
    assert row.full_name == "Иванов Иван"
    assert row.instrument_id == "complex_work_profile"
    assert row.scores["answered_count"] == 128
    assert row.birth_date == date(1998, 8, 12)
    assert row.chs == 3
    assert row.chm == 2
    assert row.scores["numerology"] == {"birth_date": "1998-08-12", "chs": 3, "chm": 2}
    assert row.quality_status in (
        "Приемлемый протокол",
        "Осторожно",
        "Критическая проверка",
        "Недостаточно данных",
    )
    response = PsychResultRead.model_validate(row).model_dump()
    assert response["behavior_preference"] == row.leading_disc
    assert response["management_focus"] == row.leading_paei
    assert response["work_style_focus"] == row.leading_work10
    assert "leading_disc" not in response
    assert "leading_paei" not in response
    assert "leading_work10" not in response
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_unknown_instrument_404():
    body = PsychResultSubmit(
        instrument_id="unknown_x",
        full_name="A",
        position="B",
        taken_at=date(2026, 8, 14),
        birth_date=date(1990, 1, 1),
        answers={"AVP-001": 3},
    )
    with pytest.raises(HTTPException) as exc:
        await mod.submit_psych_result(body, MagicMock())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_public_instrument_hides_keys():
    payload = await mod.get_public_instrument("complex_work_profile")
    assert payload["id"] == "complex_work_profile"
    assert len(payload["items"]) == 128
    assert "categories" not in payload["items"][0]
    assert "priorities" not in next(i for i in payload["items"] if i["module"] == "sjt")
