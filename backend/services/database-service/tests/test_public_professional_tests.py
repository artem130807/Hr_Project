"""TDD: public take + standalone results for platform professional (Q&A) tests."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.v1.enums import TestType as QaTestTypeEnum
from app.endpoints.v1 import public_professional_tests as mod
from app.schemas.v1.public_professional_tests import PublicTestResultSubmit


def _qa_test(*, test_id: int = 10, questions=None):
    t = MagicMock()
    t.id = test_id
    t.name = "Тест логиста"
    t.test_type = QaTestTypeEnum.questions
    t.instruction_text = "Ответьте кратко"
    t.description = "Проф. тест"
    t.duration_minutes = 30
    t.questions = questions if questions is not None else [
        MagicMock(id=1, text="Что такое логистика?", options=None, correct_option_index=None),
        MagicMock(id=2, text="Опишите маршрут", options=None, correct_option_index=None),
    ]
    return t


@pytest.mark.asyncio
async def test_get_public_test_returns_questions_without_hr_noise():
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = _qa_test()
    db.execute = AsyncMock(return_value=result)

    payload = await mod.get_public_professional_test(10, db)
    assert payload["id"] == 10
    assert payload["name"] == "Тест логиста"
    assert payload["instruction"] == "Ответьте кратко"
    assert payload["duration_minutes"] == 30
    assert len(payload["questions"]) == 2
    assert payload["questions"][0]["id"] == 1
    assert payload["questions"][0]["text"] == "Что такое логистика?"
    assert "correct_option_index" not in payload["questions"][0]
    assert "results_type" not in payload
    assert "url" not in payload


@pytest.mark.asyncio
async def test_get_public_test_rejects_url_type():
    t = _qa_test()
    t.test_type = QaTestTypeEnum.url
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = t
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(HTTPException) as exc:
        await mod.get_public_professional_test(10, db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_public_test_404_when_missing():
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(HTTPException) as exc:
        await mod.get_public_professional_test(99, db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_submit_persists_standalone_result():
    body = PublicTestResultSubmit(
        test_id=10,
        full_name="Иванов Иван",
        position="Логист",
        taken_at=date(2026, 8, 14),
        answers={"1": "Ответ А", "2": "Ответ Б"},
    )
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    async def _refresh(row):
        row.id = 5
        row.created_at = None
        row.updated_at = None
        row.test_name = "Тест логиста"

    db.refresh = AsyncMock(side_effect=_refresh)

    test_row = _qa_test()
    result = MagicMock()
    result.scalar_one_or_none.return_value = test_row
    db.execute = AsyncMock(return_value=result)

    with patch.object(mod, "PublicTestResult") as Model:
        instance = MagicMock()
        instance.full_name = "Иванов Иван"
        instance.test_id = 10
        instance.answers = {"1": "Ответ А", "2": "Ответ Б"}
        instance.position = "Логист"
        Model.return_value = instance

        row = await mod.submit_public_professional_result(body, db)

    assert row.full_name == "Иванов Иван"
    assert row.test_id == 10
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    Model.assert_called_once()
    kwargs = Model.call_args.kwargs
    assert kwargs["full_name"] == "Иванов Иван"
    assert kwargs["test_name"] == "Тест логиста"
    assert kwargs["answers"]["1"]["value"] == "Ответ А"
    assert kwargs["answers"]["2"]["value"] == "Ответ Б"
    assert "candidate_id" not in kwargs


@pytest.mark.asyncio
async def test_submit_unknown_test_404():
    body = PublicTestResultSubmit(
        test_id=404,
        full_name="A",
        position="B",
        taken_at=date(2026, 8, 14),
        answers={"1": "x"},
    )
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(HTTPException) as exc:
        await mod.submit_public_professional_result(body, db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_results_filters_by_fio_and_position():
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)

    await mod.list_public_professional_results(
        test_id=None,
        q="Иванов",
        position="Логист",
        db=db,
    )
    db.execute.assert_awaited_once()
    stmt = db.execute.await_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "ilike" in sql.lower() or "LIKE" in sql or "like" in sql.lower()


def test_submit_schema_requires_answers_and_strips():
    with pytest.raises(Exception):
        PublicTestResultSubmit(
            test_id=1,
            full_name="  ",
            position="X",
            taken_at=date(2026, 8, 14),
            answers={"1": "a"},
        )
    body = PublicTestResultSubmit(
        test_id=1,
        full_name="  Иванов  ",
        position="  Логист ",
        taken_at=date(2026, 8, 14),
        answers={"1": "ответ"},
    )
    assert body.full_name == "Иванов"
    assert body.position == "Логист"


def test_submit_schema_allows_missing_identity_when_linked():
    body = PublicTestResultSubmit(
        test_id=1,
        candidate_id=6,
        result_id=2,
        answers={"1": "ответ"},
    )
    assert body.full_name is None
    assert body.candidate_id == 6


@pytest.mark.asyncio
async def test_submit_linked_candidate_sets_pass_status():
    body = PublicTestResultSubmit(
        test_id=10,
        candidate_id=6,
        result_id=2,
        answers={"1": {"option_index": 0, "value": "A"}},
    )
    q = MagicMock(id=1, text="Q", options=["A", "B"], correct_option_index=0)
    test_row = _qa_test(questions=[q])
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=SimpleNamespace(full_name="Сергеев Артём", name="Логист"))

    candidate_result = SimpleNamespace(id=2, candidate_id=6, test_id=10, score=None)
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.side_effect = [test_row, candidate_result, None]
    db.execute = AsyncMock(return_value=execute_result)

    with patch.object(mod, "PublicTestResult", return_value=MagicMock()), patch.object(
        mod, "set_candidate_vacancy_status", new=AsyncMock(return_value=True)
    ) as set_status, patch.object(
        mod, "_identity_from_candidate", new=AsyncMock(return_value=("Сергеев Артём", "Логист"))
    ):
        await mod.submit_public_professional_result(body, db)

    set_status.assert_awaited_once()
    assert set_status.await_args.args[1] == 6
    from app.db.v1.enums import CandidateStatus
    assert set_status.await_args.args[2] == CandidateStatus.test_passed
