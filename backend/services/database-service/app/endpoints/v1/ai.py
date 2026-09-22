from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import Optional

from app.clients.api_client import APICLient, UpstreamHTTPError
from app.db.middleware import get_db
from app.dependencies import get_ai_client, get_hh_client
from app.app_logging import logger
from app.db.v1.models import (
    Vacancy, Candidate, CandidateTestResult, 
    CandidateQuestionAnswer, CandidateVacancyRelation,
    CompanyCandidateImage, DepartmentCandidateImage
)
from app.db.v1.enums import TestResultsType
from app.schemas.v1.ai import (
    VacancySummary, CandidateSummary, CandidateImageSummary, Department,
    TestGenerateRequest, TestGenerateResponse,
    VacancyDescriptionSalaryRequest, VacancyDescriptionSalaryResponse,
)
from app.utils.ai import generate_candidate_summary, generate_vacancy_description, get_company_candidate_image, get_department_candidate_image 


router = APIRouter()


@router.post("/test/generate", response_model=TestGenerateResponse)
async def proxy_test_generate(
    data: TestGenerateRequest,
    ai: Optional[APICLient] = Depends(get_ai_client),
):
    if ai is None:
        raise HTTPException(503, "AI service is not configured")
    result = await ai.post("/test/generate", json=data.model_dump())
    if result is None:
        raise HTTPException(502, "AI service unavailable")
    return result


@router.post("/vacancy/description-salary-combine", response_model=VacancyDescriptionSalaryResponse)
async def proxy_vacancy_description_salary(
    data: VacancyDescriptionSalaryRequest,
    ai: Optional[APICLient] = Depends(get_ai_client),
):
    if ai is None:
        raise HTTPException(503, "AI service is not configured")
    try:
        result = await ai.post("/vacancy/description-salary-combine",
            json=data.model_dump(),
            timeout=120.0,
            raise_http=True,
        )
    except UpstreamHTTPError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    if not result or not result.get("description"):
        raise HTTPException(502, "AI service unavailable")
    return result


@router.post(
    "/vacancy/{vacancy_id}/description-salary-combine",
    response_model=VacancyDescriptionSalaryResponse,
)
async def generate_vacancy_description_salary(
    vacancy_id: int,
    hh: Optional[APICLient] = Depends(get_hh_client),
    ai: Optional[APICLient] = Depends(get_ai_client),
    db: AsyncSession = Depends(get_db),
):
    """Save-then-generate flow: assemble vacancy facts, then one sync AI call."""
    if ai is None:
        raise HTTPException(503, "AI service is not configured")
    if hh is None:
        raise HTTPException(503, "HH service is not configured")
    vacancy_text = await generate_vacancy_description(vacancy_id, hh, db)
    try:
        result = await ai.post(
            "/vacancy/description-salary-combine",
            json={"formatted_vacancy": vacancy_text},
            timeout=120.0,
            raise_http=True,
        )
    except UpstreamHTTPError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    if not result or not result.get("description"):
        raise HTTPException(502, "AI service unavailable")
    return result


@router.post('/vacancy/{vacancy_id}/summary', response_model=VacancySummary, status_code=status.HTTP_200_OK)
async def generate_vacancy_description_endpoint(
    vacancy_id: int,
    hh: Optional[APICLient] = Depends(get_hh_client),
    db: AsyncSession = Depends(get_db)
):
    if hh is None:
        raise HTTPException(503, "HH service is not configured")
    vacancy_text = await generate_vacancy_description(vacancy_id, hh, db)
    return {"id": vacancy_id, "text": vacancy_text}


@router.post("/candidate/{candidate_id}/summary", response_model=CandidateSummary)
async def generate_candidate_summary_endpoint(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
):
    summary = await generate_candidate_summary(candidate_id, db)
    return {"id": candidate_id, "text": summary}


@router.post('/candidate-image/company/summary', response_model=CandidateImageSummary)
async def post_company_candidate_image_endpoint(db: AsyncSession = Depends(get_db)):
    summary = await get_company_candidate_image(db)

    return {"text": summary}


@router.post('/candidate-image/department/summary', response_model=CandidateImageSummary)
async def get_department_candidate_image_endpoint(
    data: Department,
    db: AsyncSession = Depends(get_db)
    ):
    summary = await get_department_candidate_image(data.department.value, db)

    return {"text": summary}
