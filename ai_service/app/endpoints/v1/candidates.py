from fastapi import APIRouter, HTTPException

from app.schemas.v1.candidates import CandidateEvaluateResponse, CandidateEvaluateSchema
from app.schemas.v1.resume import ResumeEvaluateRequest, ResumeEvaluateResponse
from app.loader import candidate_service
from app.agent.v1.errors import AIGenerationError
from app.app_logging import logger


router = APIRouter()


def _ai_or_502(result):
    if result is None:
        raise HTTPException(status_code=502, detail="AI service returned empty response")
    return result


@router.post("/candidate/evaluate", response_model=CandidateEvaluateResponse)
async def rate_candidate_endpoint(data: CandidateEvaluateSchema):
    try:
        result = await candidate_service.evaluate_candidate(
            data.candidate_summary,
            data.vacancy_summary,
            data.company_candidate_image,
            data.department_candidate_image,
        )
    except AIGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return _ai_or_502(result)


@router.post("/resume/evaluate", response_model=ResumeEvaluateResponse)
async def evaluate_resume_endpoint(data: ResumeEvaluateRequest):
    logger.info("/resume/evaluate input received")
    try:
        result = await candidate_service.evaluate_resume(
            data.resume_str,
            data.vacancy_str,
        )
    except AIGenerationError as e:
        logger.info("/resume/evaluate AI error: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.info("/resume/evaluate error: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _ai_or_502(result)
