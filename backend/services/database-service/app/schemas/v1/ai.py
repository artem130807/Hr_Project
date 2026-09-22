from typing import Optional
from pydantic import BaseModel, Field

from app.db.v1.enums import Departments

class AIVacancyDescpriptionResponse(BaseModel):
    description: str = Field(..., example='Описание вакансии логиста...')


class AIVacnacySalaryResponse(BaseModel):
    name: str = Field(..., example='Логист')
    salary_from: Optional[int] = Field(default=None, example=30000)
    salary_to: Optional[int] = Field(default=None, example=50000)
    currency_id: Optional[str] = Field(default=None, example='RUR')


class VacancySummary(BaseModel):
    id: int = Field(..., example=1)
    text: str = Field(..., example='Some formatted vacancy fields...')


class CandidateSummary(BaseModel):
    id: int = Field(..., example=1)
    text: str = Field(..., example='Some formatted candidate fields...')


class CandidateImageSummary(BaseModel):
    text: str = Field(..., example='Умный, работящий')


class Department(BaseModel):
    department: Departments = Field(..., examples=[Departments.hr.value])


class TestGenerateRequest(BaseModel):
    topic: str = Field(..., examples=["Стрессоустойчивость"])
    formatted_vacancy: str = Field(..., examples=["Software Engineer..."])


class TestGenerateResponse(BaseModel):
    name: str
    description: str
    instruction: str
    questions: list[dict]


class VacancyDescriptionSalaryRequest(BaseModel):
    formatted_vacancy: str = Field(..., min_length=20, examples=["Software Engineer..."])


class VacancyDescriptionSalaryResponse(BaseModel):
    description: str
    salary_from: Optional[float] = None
    salary_to: Optional[float] = None