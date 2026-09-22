"""Endpoint handlers with mocked services (no OpenAI / JWKS)."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from app.agent.v1.errors import AIGenerationError
from app.schemas.v1.vacancies import (
    VacancyData,
    VacancyDescriptionResponse,
    VacancySalaryPreciseResponse,
    VacancyDescriptionSalaryCombineResponse,
    VacancyDescriptionSalaryRequest,
)
from app.schemas.v1.candidates import CandidateEvaluateSchema, CandidateEvaluateResponse
from app.schemas.v1.resume import ResumeEvaluateRequest, ResumeEvaluateResponse
from app.schemas.v1.tests import TestGenerateSchema, TestGenerateResponse, TestQuestion


@pytest.mark.asyncio
async def test_generate_vacancy_endpoint_ok():
    from app.endpoints.v1 import vacancies as mod

    with patch.object(
        mod.vacancy_service,
        "generate_description",
        new=AsyncMock(return_value=VacancyDescriptionResponse(description="x" * 220)),
    ):
        result = await mod.generate_vacancy_endpoint(
            VacancyData(formatted_vacancy="Логист")
        )
    assert len(result.description) >= 200


@pytest.mark.asyncio
async def test_generate_vacancy_endpoint_ai_error_502():
    from app.endpoints.v1 import vacancies as mod

    with patch.object(
        mod.vacancy_service,
        "generate_description",
        new=AsyncMock(side_effect=AIGenerationError("boom")),
    ):
        with pytest.raises(HTTPException) as exc:
            await mod.generate_vacancy_endpoint(VacancyData(formatted_vacancy="x"))
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_precise_salary_endpoint_ok():
    from app.endpoints.v1 import vacancies as mod

    with patch.object(
        mod.vacancy_service,
        "precise_salary",
        new=AsyncMock(
            return_value=VacancySalaryPreciseResponse(salary_from=100, salary_to=200)
        ),
    ):
        result = await mod.precise_salary_endpoint(VacancyData(formatted_vacancy="x"))
    assert result.salary_from == 100


@pytest.mark.asyncio
async def test_combine_endpoint_ok():
    from app.endpoints.v1 import vacancies as mod

    with patch.object(
        mod.vacancy_service,
        "combine_description_and_salary",
        new=AsyncMock(
            return_value=VacancyDescriptionSalaryCombineResponse(
                description="d", salary_from=1, salary_to=2
            )
        ),
    ):
        result = await mod.combine_description_salary_endpoint(
            VacancyDescriptionSalaryRequest(
                formatted_vacancy="Логист, Москва, опыт от 3 лет, перевозки"
            )
        )
    assert result.description == "d"


@pytest.mark.asyncio
async def test_combine_timeout_504(monkeypatch):
    import asyncio
    from app.endpoints.v1 import vacancies as mod

    async def hang(_text):
        await asyncio.sleep(1)

    monkeypatch.setattr(mod, "AI_GENERATE_TIMEOUT_SECONDS", 0.01)
    with patch.object(mod.vacancy_service, "combine_description_and_salary", new=hang):
        with pytest.raises(HTTPException) as exc:
            await mod.combine_description_salary_endpoint(
                VacancyDescriptionSalaryRequest(
                    formatted_vacancy="Логист, Москва, опыт от 3 лет, перевозки"
                )
            )
    assert exc.value.status_code == 504


@pytest.mark.asyncio
async def test_candidate_evaluate_endpoint_ok():
    from app.endpoints.v1 import candidates as mod

    with patch.object(
        mod.candidate_service,
        "evaluate_candidate",
        new=AsyncMock(return_value=CandidateEvaluateResponse(comment="ok", score=90)),
    ):
        result = await mod.rate_candidate_endpoint(
            CandidateEvaluateSchema(
                candidate_summary="c",
                vacancy_summary="v",
                company_candidate_image="",
                department_candidate_image="",
            )
        )
    assert result.score == 90


@pytest.mark.asyncio
async def test_resume_evaluate_endpoint_ok():
    from app.endpoints.v1 import candidates as mod

    with patch.object(
        mod.candidate_service,
        "evaluate_resume",
        new=AsyncMock(return_value=ResumeEvaluateResponse(score=55, comment="m")),
    ):
        result = await mod.evaluate_resume_endpoint(
            ResumeEvaluateRequest(resume_str="r", vacancy_str="v")
        )
    assert result.score == 55


@pytest.mark.asyncio
async def test_resume_evaluate_endpoint_ai_error_502():
    from app.endpoints.v1 import candidates as mod

    with patch.object(
        mod.candidate_service,
        "evaluate_resume",
        new=AsyncMock(side_effect=AIGenerationError("fail")),
    ):
        with pytest.raises(HTTPException) as exc:
            await mod.evaluate_resume_endpoint(
                ResumeEvaluateRequest(resume_str="r", vacancy_str="v")
            )
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_test_generate_endpoint_ok():
    from app.endpoints.v1 import tests as mod

    with patch.object(
        mod.test_service,
        "generate_test",
        new=AsyncMock(
            return_value=TestGenerateResponse(
                name="N",
                description="D",
                instruction="I",
                questions=[TestQuestion(text="Q")],
            )
        ),
    ):
        result = await mod.test_generate_endpoint(
            TestGenerateSchema(topic="стресс", formatted_vacancy="vac")
        )
    assert result.name == "N"
    assert len(result.questions) == 1


def test_router_paths_registered():
    from app.endpoints.v1.vacancies import router as vacancy_router
    from app.endpoints.v1.candidates import router as candidate_router
    from app.endpoints.v1.tests import router as test_router
    from app.endpoints.v1.auth import router as auth_router

    def paths(r):
        return {getattr(route, "path", None) for route in r.routes}

    assert "/vacancy/description/generate" in paths(vacancy_router)
    assert "/vacancy/salary-precise" in paths(vacancy_router)
    assert "/vacancy/description-salary-combine" in paths(vacancy_router)
    assert "/candidate/evaluate" in paths(candidate_router)
    assert "/resume/evaluate" in paths(candidate_router)
    assert "/test/generate" in paths(test_router)
    assert "/token/user" in paths(auth_router)
