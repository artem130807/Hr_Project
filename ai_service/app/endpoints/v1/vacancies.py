import asyncio

from fastapi import APIRouter, HTTPException

from app.loader import vacancy_service
from app.agent.v1.errors import AIGenerationError
from app.app_logging import logger
from app.config import AI_GENERATE_TIMEOUT_SECONDS
from app.schemas.v1.vacancies import (
    VacancyDescriptionResponse,
    VacancyDescriptionSalaryCombineResponse,
    VacancyDescriptionSalaryRequest,
    VacancySalaryPreciseResponse,
    VacancyData,
)

router = APIRouter()


def _ai_or_502(result):
    if result is None:
        raise HTTPException(status_code=502, detail="AI service returned empty response")
    return result


async def _run_generate(coro):
    try:
        return await asyncio.wait_for(coro, timeout=AI_GENERATE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        logger.warning("Vacancy AI generation timed out after %ss", AI_GENERATE_TIMEOUT_SECONDS)
        raise HTTPException(status_code=504, detail="AI generation timed out") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIGenerationError as exc:
        logger.warning("Vacancy AI generation failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/vacancy/description/generate", response_model=VacancyDescriptionResponse)
async def generate_vacancy_endpoint(data: VacancyData):
    result = await _run_generate(
        vacancy_service.generate_description(vacancy_text=data.formatted_vacancy)
    )
    return _ai_or_502(result)


@router.post("/vacancy/salary-precise", response_model=VacancySalaryPreciseResponse)
async def precise_salary_endpoint(data: VacancyData):
    result = await _run_generate(
        vacancy_service.precise_salary(vacancy_text=data.formatted_vacancy)
    )
    return _ai_or_502(result)


@router.post(
    "/vacancy/description-salary-combine",
    response_model=VacancyDescriptionSalaryCombineResponse,
)
async def combine_description_salary_endpoint(data: VacancyDescriptionSalaryRequest):
    """Synchronous HR contract: description + salary band from vacancy facts."""
    result = await _run_generate(
        vacancy_service.combine_description_and_salary(data.formatted_vacancy)
    )
    return _ai_or_502(result)
