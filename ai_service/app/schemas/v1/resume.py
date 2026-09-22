from pydantic import BaseModel, ConfigDict, Field


class ResumeEvaluateRequest(BaseModel):
    resume_str: str
    vacancy_str: str


class ResumeEvaluateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float = Field(..., ge=0, le=100)
    comment: str
