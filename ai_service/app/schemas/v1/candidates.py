from pydantic import BaseModel, ConfigDict, Field


class CandidateEvaluateSchema(BaseModel):
    candidate_summary: str
    vacancy_summary: str
    company_candidate_image: str = ""
    department_candidate_image: str = ""


class CandidateEvaluateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comment: str
    score: float = Field(..., ge=0, le=100)
