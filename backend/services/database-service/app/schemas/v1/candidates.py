from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.db.v1.enums import MaritalStatus, Gender, WorkExpirience, UpdateDate, CandidateStatus, CandidateStage, Departments
from app.schemas.v1.vacancies import ReadVacancy

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
    ai_score: Optional[float] = Field(None, description="AI score 0–100", example=87.0)
    hr_comment: Optional[str] = Field(None, description="HR comment for the candidate", example="Хороший кандидат")
    next_contact_at: Optional[datetime] = Field(None, description="Дата следующего контакта")
    next_contact_owner_id: Optional[str] = Field(None, max_length=36)
    next_contact_owner_name: Optional[str] = Field(None, max_length=200)

    stage: CandidateStage = Field(..., description="Стадия найма", example=CandidateStage.employment.value)


class CandidateRead(BaseCandidate):
    id: int = Field(example=142)
    user_id: Optional[int] = Field(description='bot_user.id', example=429)
    current_status: Optional[str] = None
    is_perfect_candidate: bool = False
    last_vacancy_id: Optional[int] = Field(None, description="ID последней вакансии (действующей или той, после которой кандидат был archieved/blacklisted)", example=1)
    last_vacancy_title: Optional[str] = Field(None, description="Название последней вакансии (действующей или той, после которой кандидат был archieved/blacklisted)", example="Механик")

    created_at: datetime

    class Config:
        from_attributes = True


class CandidateCreate(BaseCandidate):
    pass


class CandidateUpdate(BaseModel):
    user_id: Optional[int] = None
    birth_date: Optional[date] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = Field(default=None, min_length=12, max_length=12)
    telegram_username: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=254)
    marital_status: Optional[MaritalStatus] = None
    hobbies: Optional[list[str]] = None
    age: Optional[int] = None
    gender: Optional[Gender] = None
    personal_characteristics: Optional[str] = None

    hh_resume_link: Optional[str] = None

    languages: Optional[list[str]] = None
    relevant_position_expirience: Optional[str] = None
    certain_position_expirience: Optional[str] = None
    total_work_expirience: Optional[WorkExpirience] = None
    other_work_expirience: Optional[list[str]] = None
    average_service_length: Optional[float] = None
    education: Optional[list[str]] = None
    hard_skills: Optional[list[str]] = None
    work_programs: Optional[list[str]] = None
    resume_update_date: Optional[UpdateDate] = None
    active_search: Optional[bool] = None
    salary_expectations: Optional[int] = None
    ai_comment: Optional[str] = None
    ai_score: Optional[float] = None
    hr_comment: Optional[str] = Field(None, description="HR comment for the candidate", example="Хороший кандидат")
    next_contact_at: Optional[datetime] = None
    next_contact_owner_id: Optional[str] = Field(default=None, max_length=36)
    next_contact_owner_name: Optional[str] = Field(default=None, max_length=200)
    stage: Optional[CandidateStage] = None


class BaseCandidateVacancyRelation(BaseModel):
    candidate_id: int = Field(..., example=1)
    vacancy_id: int = Field(..., example=1)
    status: CandidateStatus = Field(..., example=CandidateStatus.applied.value)
    is_active: bool = Field(..., example=True)


class CreateCandidateVacancyRelation(BaseCandidateVacancyRelation):
    pass


class CandidateVacancyRelationUpdate(BaseModel):
    status: Optional[CandidateStatus] = None
    is_active: Optional[bool] = None


class ReadCandidateVacancyRelation(BaseCandidateVacancyRelation):
    id: int = Field(..., example=1)
    candidate: CandidateRead
    vacancy: ReadVacancy


class CandidateStatusSchema(BaseModel):
    status: CandidateStatus = Field(..., example=CandidateStatus.applied.value)


class CandidateFillInfoSchema(BaseModel):
    candidate_id: int = Field(..., example=1)


class CandidateHTMLSchema(BaseModel):
    candidate_id: int = Field(..., example=1)


class CandidateHTMLResponse(BaseModel):
    text: str = Field(..., example='Some html for telegram')


class ChangeVacancyData(BaseModel):
    candidate_id: int = Field(..., example=1)
    vacancy_id: int = Field(..., example=2)


class CandidateHhLookupItem(BaseModel):
    resume_id: Optional[str] = None
    candidate_id: int
    matched_by: str = Field(..., examples=["resume", "phone", "email"])


class CandidateHhLookupResponse(BaseModel):
    items: list[CandidateHhLookupItem] = Field(default_factory=list)
