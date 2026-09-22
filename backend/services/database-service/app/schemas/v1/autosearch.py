from typing import Optional
from pydantic import BaseModel, Field
from app.db.v1.enums import ResumeSearchStatus, EvaluationStatus

class SearchItemBase(BaseModel):
    vacancy_id: int = Field(..., examples=[10, 20, 30])
    daily_limit: int = Field(..., examples=[30, 250, 500])
    sent_today: int = Field(..., examples=[30, 250, 500])
    total_sent: int = Field(..., examples=[3, 24, 53])
    active: bool = Field(..., example=True)
    invite_limit: int = Field(default=10, examples=[10, 20, 30])  # Количество приглашений для отправки


class SearchItemCreate(SearchItemBase):
    pass


class SearchItemRead(SearchItemBase):
    id: int = Field(..., examples=[1, 2, 3])


class SearchItemUpdate(BaseModel):
    vacancy_id: Optional[int] = None
    daily_limit: Optional[int] = None
    sent_today: Optional[int] = None
    total_sent: Optional[int] = None
    active: Optional[bool] = None
    invite_limit: Optional[int] = None


class ReviewedResumeBase(BaseModel):
    auto_search_id: int = Field(..., examples=[1, 2])
    resume_id: str = Field(..., examples=["1", "2", "3"])
    status: ResumeSearchStatus = Field(..., examples=[ResumeSearchStatus.invited.value, ResumeSearchStatus.skipped.value])
    score: Optional[float] = Field(default=None, examples=[85.5, 92.0, 67.3])  # Оценка от AI (0-100)
    evaluation_status: EvaluationStatus = Field(default=EvaluationStatus.pending, examples=[EvaluationStatus.pending.value, EvaluationStatus.evaluated.value])


class ReviewedResumeCreate(ReviewedResumeBase):
    pass


class ReviewedResumeRead(ReviewedResumeBase):
    id: int = Field(..., examples=[1, 2])


class ReviewedResumeUpdate(BaseModel):
    auto_search_id: Optional[int] = None
    resume_id: Optional[str] = None
    status: Optional[ResumeSearchStatus] = None
    score: Optional[float] = None
    evaluation_status: Optional[EvaluationStatus] = None


class ResumeExists(BaseModel):
    exists: bool