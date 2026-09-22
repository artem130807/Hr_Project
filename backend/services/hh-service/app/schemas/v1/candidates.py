from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.enums.v1.enums import MaritalStatus, Gender, WorkExpirience, UpdateDate, CandidateStatus, CandidateStage, Departments

class BaseCandidate(BaseModel):
    # личные данные
    birth_date: Optional[date] = Field(None, example="1990-05-15")
    full_name: Optional[str] = Field(None, example="Иванов Иван Иванович")
    phone_number: Optional[str] = Field(
        None, min_length=10, max_length=20, example="+79225536715"
    )
    telegram_username: Optional[str] = Field(None, max_length=64, example="@nickname")
    email: Optional[str] = Field(None, max_length=254, example="ivan@example.com")
    marital_status: Optional[MaritalStatus] = Field(None, example=MaritalStatus.married.value)
    hobbies: List[str] = Field(default_factory=list, example=["чтение", "бег"])
    age: Optional[int] = Field(None, example=35)
    gender: Optional[Gender] = Field(None, example=Gender.male.value)
    personal_characteristics: Optional[str] = Field(None, example="Ответственный, коммуникабельный")

    hh_resume_link: str = Field(..., example="https://hh.ru/resume/1029381")

    # общие данные
    languages: List[str] = Field(default_factory=list, example=["Английский", "Немецкий"])
    relevant_position_expirience: Optional[str] = Field(None, example="Опыт в логистике от 2 лет")
    certain_position_expirience: Optional[str] = Field(None, example="Менеджер по логистике 3 года")
    total_work_expirience: Optional[WorkExpirience] = Field(None, example=WorkExpirience.one_to_three.value)
    other_work_expirience: List[str] = Field(default_factory=list, example=["Водитель 2 года"])
    average_service_length: Optional[float] = Field(None, description="Средний срок работы в компании, лет", example=1.5)
    education: List[str] = Field(default_factory=list, example=["МГУ", "Факультет ВМК"])
    hard_skills: List[str] = Field(default_factory=list, example=["Python", "SQL"])
    work_programs: List[str] = Field(default_factory=list, example=["Excel", "1C"])
    resume_update_date: Optional[UpdateDate] = Field(None, example=UpdateDate.month.value)
    active_search: Optional[bool] = Field(None, example=True)
    salary_expectations: Optional[int] = Field(None, example=120000)
    ai_comment: Optional[str] = Field(None, description="AI comment for the candidate", example="A+")
    ai_score: Optional[float] = Field(None, description="AI score for the candidate", example=5.0)

    stage: CandidateStage = Field(..., description="Стадия найма", example=CandidateStage.employment.value)


class CandidateRead(BaseCandidate):
    id: int = Field(example=142)
    user_id: Optional[int] = Field(description='bot_user.id', example=429)


class CandidateCreate(BaseCandidate):
    pass