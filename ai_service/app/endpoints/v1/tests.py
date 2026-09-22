from fastapi import APIRouter, HTTPException

from app.schemas.v1.tests import TestGenerateResponse, TestGenerateSchema
from app.loader import test_service
from app.agent.v1.errors import AIGenerationError

router = APIRouter()


@router.post("/test/generate", response_model=TestGenerateResponse)
async def test_generate_endpoint(data: TestGenerateSchema):
    try:
        result = await test_service.generate_test(data.topic, data.formatted_vacancy)
    except AIGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    if result is None:
        raise HTTPException(status_code=502, detail="AI service returned empty response")
    return result
