from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.endpoints.v1 import ai as ep
from app.schemas.v1.ai import VacancyDescriptionSalaryRequest


@pytest.mark.asyncio
async def test_proxy_combine_requires_ai_client():
    with pytest.raises(HTTPException) as exc:
        await ep.proxy_vacancy_description_salary(
            VacancyDescriptionSalaryRequest(formatted_vacancy="Логист Москва опыт 3 года перевозки"),
            ai=None,
        )
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_proxy_combine_posts_to_ai_service():
    ai = AsyncMock()
    ai.post = AsyncMock(
        return_value={"description": "d" * 220, "salary_from": 100000, "salary_to": 150000}
    )
    result = await ep.proxy_vacancy_description_salary(
        VacancyDescriptionSalaryRequest(formatted_vacancy="Логист Москва опыт 3 года перевозки"),
        ai=ai,
    )
    assert result["salary_from"] == 100000
    kwargs = ai.post.await_args
    assert kwargs.args[0] == "/vacancy/description-salary-combine"
    assert kwargs.kwargs["timeout"] == 120.0
    assert kwargs.kwargs["raise_http"] is True


@pytest.mark.asyncio
async def test_generate_for_saved_vacancy_assembles_facts_then_calls_ai():
    ai = AsyncMock()
    ai.post = AsyncMock(
        return_value={"description": "d" * 220, "salary_from": 80_000, "salary_to": 120_000}
    )
    hh = AsyncMock()
    db = AsyncMock()
    with patch.object(
        ep,
        "generate_vacancy_description",
        new=AsyncMock(return_value="Название: логист\nРегион: Москва\nОпыт: 3 года"),
    ) as facts:
        result = await ep.generate_vacancy_description_salary(42, hh=hh, ai=ai, db=db)
    facts.assert_awaited_once()
    payload = ai.post.await_args.kwargs["json"]["formatted_vacancy"]
    assert "логист" in payload
    assert result["salary_to"] == 120_000


@pytest.mark.asyncio
async def test_generate_maps_ai_auth_failure_to_502():
    ai = AsyncMock()
    ai.post = AsyncMock(
        side_effect=ep.UpstreamHTTPError(502, "AI service auth failed: Could not validate credentials")
    )
    hh = AsyncMock()
    db = AsyncMock()
    with patch.object(
        ep,
        "generate_vacancy_description",
        new=AsyncMock(return_value="Название: логист\nРегион: Москва"),
    ):
        with pytest.raises(HTTPException) as exc:
            await ep.generate_vacancy_description_salary(12, hh=hh, ai=ai, db=db)
    assert exc.value.status_code == 502
    assert "AI service" in str(exc.value.detail)
