"""Vacancy / Candidate / Test AI services with mocked AIClient."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agent.v1.services.vacancy_service import VacancyAIService, normalize_description_salary
from app.agent.v1.services.candidate_service import CandidateAIService
from app.agent.v1.services.test_service import TestAIService
from app.schemas.v1.vacancies import (
    VacancyDescriptionResponse,
    VacancySalaryPreciseResponse,
    VacancyDescriptionSalaryCombineResponse,
)
from app.schemas.v1.candidates import CandidateEvaluateResponse
from app.schemas.v1.resume import ResumeEvaluateResponse
from app.schemas.v1.tests import TestGenerateResponse, TestQuestion


@pytest.mark.asyncio
async def test_vacancy_generate_description():
    ai = MagicMock()
    ai.generate = AsyncMock(
        return_value=VacancyDescriptionResponse(description="d" * 250)
    )
    svc = VacancyAIService(ai)
    result = await svc.generate_description("Логист, Москва")
    assert result.description.startswith("d")
    assert ai.generate.await_args.kwargs["output_model"] is VacancyDescriptionResponse


@pytest.mark.asyncio
async def test_vacancy_precise_salary_uses_web_flag():
    ai = MagicMock()
    ai.generate = AsyncMock(
        return_value=VacancySalaryPreciseResponse(salary_from=100000, salary_to=150000)
    )
    svc = VacancyAIService(ai)
    result = await svc.precise_salary("Водитель")
    assert result.salary_from == 100000
    assert ai.generate.await_args.kwargs["use_web_search"] is True


@pytest.mark.asyncio
async def test_vacancy_combine():
    ai = MagicMock()
    ai.generate = AsyncMock(
        return_value=VacancyDescriptionSalaryCombineResponse(
            description="d" * 250, salary_from=150000.4, salary_to=90000.2
        )
    )
    svc = VacancyAIService(ai)
    result = await svc.combine_description_and_salary(
        "Название: логист. Регион: Москва. Опыт: 3 года. Задачи: перевозки."
    )
    assert result.description.startswith("d")
    assert result.salary_from == 90000
    assert result.salary_to == 150000
    assert ai.generate.await_count == 1
    assert ai.generate.await_args.kwargs["output_model"] is VacancyDescriptionSalaryCombineResponse


@pytest.mark.asyncio
async def test_vacancy_combine_retries_short_description():
    ai = MagicMock()
    ai.generate = AsyncMock(
        side_effect=[
            VacancyDescriptionSalaryCombineResponse(description="коротко", salary_from=1, salary_to=2),
            VacancyDescriptionSalaryCombineResponse(description="d" * 220, salary_from=100000, salary_to=140000),
        ]
    )
    svc = VacancyAIService(ai)
    result = await svc.combine_description_and_salary(
        "Название: логист. Регион: Москва. Опыт: 3 года. Задачи: перевозки."
    )
    assert len(result.description) >= 200
    assert ai.generate.await_count == 2


def test_normalize_description_salary_swaps_and_strips():
    out = normalize_description_salary(
        VacancyDescriptionSalaryCombineResponse(
            description="  hello  ", salary_from=200, salary_to=100
        )
    )
    assert out.description == "hello"
    assert out.salary_from == 100
    assert out.salary_to == 200


@pytest.mark.asyncio
async def test_candidate_evaluate_includes_portraits_in_prompt():
    ai = MagicMock()
    ai.generate = AsyncMock(
        return_value=CandidateEvaluateResponse(comment="ok", score=80)
    )
    svc = CandidateAIService(ai)
    result = await svc.evaluate_candidate("cand", "vac", "company-portrait", "dept-portrait")
    assert result.score == 80
    prompt = ai.generate.await_args.kwargs["prompt"]
    assert "company-portrait" in prompt
    assert "dept-portrait" in prompt
    assert "Вакансия:" in prompt
    assert "Кандидат:" in prompt


@pytest.mark.asyncio
async def test_resume_evaluate():
    ai = MagicMock()
    ai.generate = AsyncMock(
        return_value=ResumeEvaluateResponse(score=70, comment="fair")
    )
    svc = CandidateAIService(ai)
    result = await svc.evaluate_resume("resume", "vacancy")
    assert result.score == 70


@pytest.mark.asyncio
async def test_test_generate_returns_structured():
    ai = MagicMock()
    ai.generate = AsyncMock(
        return_value=TestGenerateResponse(
            name="T",
            description="D",
            instruction="I",
            questions=[TestQuestion(text="Q1")],
        )
    )
    svc = TestAIService(ai)
    result = await svc.generate_test("стресс", "vacancy text")
    assert isinstance(result, TestGenerateResponse)
    assert result.questions[0].text == "Q1"
