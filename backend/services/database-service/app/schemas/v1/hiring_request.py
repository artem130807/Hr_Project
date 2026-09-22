from typing import Annotated, List, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field
from app.db.v1.enums import Departments, TestType, TestResultsType, HiringRequestStatus


class EmployeeRequestBase(BaseModel):
    # General Info
    position: str = Field(..., example="Senior Backend Developer")
    department: Departments = Field(..., example=Departments.it)
    headcount: Annotated[int, Field(ge=1, example=2)]
    planned_start_date: Optional[str] = Field(None, example="2025-02-01")
    urgency: Optional[str] = Field(None, example="high")

    # Contact Info
    manager_name: str = Field(..., example="РРІР°РЅРѕРІ РРІР°РЅ")
    manager_position: str = Field(..., example="CTO")
    phone: str = Field(..., example="+7 (999) 123-45-67")
    backup_contact: Optional[str] = Field(None, example="РџРµС‚СЂРѕРІ РџРµС‚СЂ, @petrov")

    # Opening Reason
    reason: Optional[str] = Field(None, example="expansion")
    previous_employee: Optional[str] = Field(None, example="РЎРёРґРѕСЂРѕРІ РЎ.")
    probation_period: Optional[int] = Field(None, example=3)

    # Job Description
    purpose: str = Field(..., example="Р Р°Р·СЂР°Р±РѕС‚РєР° Рё РїРѕРґРґРµСЂР¶РєР° РјРёРєСЂРѕСЃРµСЂРІРёСЃРѕРІ")
    features: Optional[str] = Field(None, example="Р Р°Р±РѕС‚Р° СЃ legacy РєРѕРґРѕРј")
    reporting: Optional[str] = Field(None, example="РўРµС…РЅРёС‡РµСЃРєРѕРјСѓ РґРёСЂРµРєС‚РѕСЂСѓ")
    horizontal_connections: Optional[str] = Field(None, example="Frontend, DevOps")
    growth_prospects: Optional[str] = Field(None, example="Team Lead С‡РµСЂРµР· 1 РіРѕРґ")

    # Tasks
    daily_tasks: Optional[List[str]] = Field(None, example=["Р Р°Р·СЂР°Р±РѕС‚РєР° РЅРѕРІС‹С… С„РёС‡", "Code review"])
    weekly_tasks: Optional[List[str]] = Field(None, example=["РџР»Р°РЅРёСЂРѕРІР°РЅРёРµ СЃРїСЂРёРЅС‚Р°"])
    project_tasks: Optional[List[str]] = Field(None, example=["РњРёРіСЂР°С†РёСЏ РЅР° РјРёРєСЂРѕСЃРµСЂРІРёСЃС‹"])

    # KPI
    kpi_metrics: Optional[List[str]] = Field(None, example=["Velocity +20%"])
    expected_results_probation: Optional[List[str]] = Field(None, example=["5 С„РёС‡ СЂР°Р·СЂР°Р±РѕС‚Р°РЅРѕ"])
    priorities_3months: Optional[List[str]] = Field(None, example=["РР·СѓС‡РёС‚СЊ РєРѕРґРѕРІСѓСЋ Р±Р°Р·Сѓ"])

    # Requirements
    mandatory_requirements: List[str] = Field(..., example=["РћРїС‹С‚ Python 5 Р»РµС‚"])
    desired_requirements: Optional[List[str]] = Field(None, example=["Р—РЅР°РЅРёРµ Go"])
    age_from: Optional[int] = Field(None, example=25)
    age_to: Optional[int] = Field(None, example=40)
    gender: Optional[str] = Field(None, example="РјСѓР¶С‡РёРЅР°")
    total_experience_years: Optional[int] = Field(None, example=7)
    relevant_experience_years: Optional[int] = Field(None, example=5)

    # Hard/Soft Skills
    required_hard_skills: Optional[List[str]] = Field(None, example=["Python", "FastAPI"])
    optional_hard_skills: Optional[List[str]] = Field(None, example=["Docker", "Kubernetes"])
    required_soft_skills: Optional[List[str]] = Field(None, example=["РљРѕРјР°РЅРґРЅР°СЏ СЂР°Р±РѕС‚Р°"])
    unacceptable_soft_skills: Optional[List[str]] = Field(None, example=["РўРѕРєСЃРёС‡РЅРѕСЃС‚СЊ"])

    # Competencies / Values
    job_competencies: Optional[List[str]] = Field(None, example=["Code review"])
    corporate_competencies: Optional[List[str]] = Field(None, example=["РћС‚РІРµС‚СЃС‚РІРµРЅРЅРѕСЃС‚СЊ"])
    critical_values: Optional[List[str]] = Field(None, example=["РљР°С‡РµСЃС‚РІРѕ РєРѕРґР°"])
    acceptable_behavior: Optional[List[str]] = Field(None, example=["Р—Р°РґР°РІР°С‚СЊ РІРѕРїСЂРѕСЃС‹"])
    unacceptable_behavior: Optional[List[str]] = Field(None, example=["РЎРїРѕСЂС‹ Р±РµР· РїСЂРёС‡РёРЅС‹"])
    fit_indicators: Optional[List[str]] = Field(None, example=["РђРєС‚РёРІРЅРѕРµ СѓС‡Р°СЃС‚РёРµ РІ code review"])
    misfit_indicators: Optional[List[str]] = Field(None, example=["РџРѕСЃС‚РѕСЏРЅРЅС‹Рµ СЃРїРѕСЂС‹"])

    # Technical Requirements
    software: Optional[List[str]] = Field(None, example=["Python 3.11+", "FastAPI"])
    tools: Optional[List[str]] = Field(None, example=["Jira", "Slack"])
    languages: Optional[List[str]] = Field(None, example=["English B2"])
    appearance: Optional[str] = Field(None, example="РЎРІРѕР±РѕРґРЅС‹Р№ СЃС‚РёР»СЊ")

    # Search Strategy
    keywords: Optional[List[str]] = Field(None, example=["Python developer"])
    similar_positions: Optional[List[str]] = Field(None, example=["Backend Developer"])
    stop_companies: Optional[List[str]] = Field(None, example=["Company A"])
    donor_companies: Optional[List[str]] = Field(None, example=["Company B"])
    referral_sources: Optional[List[str]] = Field(None, example=["LinkedIn"])

    # Work Conditions
    schedule: str = Field(..., example="Р“РёР±РєРёР№ РіСЂР°С„РёРє")
    work_format: str = Field(..., example="hybrid")
    work_address: Optional[str] = Field(None, max_length=500, example="г. Москва, ул. Примерная, 1")
    background_search: bool = Field(False, description="Фоновый подбор сверх текущей потребности")
    work_day_description: Optional[str] = Field(None, example="2-3 РґРЅСЏ РІ РѕС„РёСЃРµ, РѕСЃС‚Р°Р»СЊРЅРѕРµ СѓРґР°Р»С‘РЅРЅРѕ")
    business_trips_required: Optional[bool] = Field(None, example=False)
    business_trips_frequency: Optional[str] = Field(None, example="1-2 СЂР°Р·Р° РІ РіРѕРґ")
    business_trips_locations: Optional[str] = Field(None, example="РљРѕРЅС„РµСЂРµРЅС†РёРё")
    salary_from: Optional[int] = Field(None, example=250000)
    salary_to: Optional[int] = Field(None, example=350000)
    currency: Optional[str] = Field(None, example="RUB")
    gross: Optional[bool] = Field(None, example=True)
    bonus_type: Optional[str] = Field(None, example="Р“РѕРґРѕРІРѕР№")
    bonus_amount: Optional[str] = Field(None, example="2 РѕРєР»Р°РґР°")
    bonus_conditions: Optional[str] = Field(None, example="РџРѕ KPI")
    benefits: Optional[List[str]] = Field(None, example=["РњРµРґСЃС‚СЂР°С…РѕРІРєР°", "РЎРїРѕСЂС‚Р·Р°Р»"])

    # Test Assignment
    test_required: Optional[bool] = Field(None, example=True)
    test_description: Optional[str] = Field(None, example="Р Р°Р·СЂР°Р±РѕС‚Р°С‚СЊ REST API")
    test_deadline: Optional[str] = Field(None, example="5 СЂР°Р±РѕС‡РёС… РґРЅРµР№")
    test_is_paid: Optional[bool] = Field(None, example=False)

    # Status
    status: HiringRequestStatus = Field(..., example=HiringRequestStatus.created)
    planned_close_date: Optional[date] = Field(None, example="2026-09-01")
    initiator_name: Optional[str] = Field(None, example="Иванов И.И.")
    linked_vacancy_id: Optional[int] = Field(None, example=12)


class EmployeeRequestCreate(EmployeeRequestBase):
    pass


class HiringRequestInviteRead(BaseModel):
    url: str
    expires_at: datetime


class PublicHiringRequestInviteRead(BaseModel):
    expires_at: datetime


class PublicHiringRequestSubmitted(BaseModel):
    id: int
    public_code: str
    status: HiringRequestStatus


class EmployeeRequestUpdate(BaseModel):
    """Partial update for hiring request body (status via dedicated endpoint)."""

    position: Optional[str] = None
    department: Optional[Departments] = None
    headcount: Optional[int] = None
    planned_start_date: Optional[str] = None
    urgency: Optional[str] = None
    manager_name: Optional[str] = None
    manager_position: Optional[str] = None
    phone: Optional[str] = None
    backup_contact: Optional[str] = None
    reason: Optional[str] = None
    previous_employee: Optional[str] = None
    probation_period: Optional[int] = None
    purpose: Optional[str] = None
    features: Optional[str] = None
    reporting: Optional[str] = None
    horizontal_connections: Optional[str] = None
    growth_prospects: Optional[str] = None
    daily_tasks: Optional[List[str]] = None
    weekly_tasks: Optional[List[str]] = None
    project_tasks: Optional[List[str]] = None
    kpi_metrics: Optional[List[str]] = None
    expected_results_probation: Optional[List[str]] = None
    priorities_3months: Optional[List[str]] = None
    mandatory_requirements: Optional[List[str]] = None
    desired_requirements: Optional[List[str]] = None
    age_from: Optional[int] = None
    age_to: Optional[int] = None
    gender: Optional[str] = None
    total_experience_years: Optional[int] = None
    relevant_experience_years: Optional[int] = None
    required_hard_skills: Optional[List[str]] = None
    optional_hard_skills: Optional[List[str]] = None
    required_soft_skills: Optional[List[str]] = None
    unacceptable_soft_skills: Optional[List[str]] = None
    job_competencies: Optional[List[str]] = None
    corporate_competencies: Optional[List[str]] = None
    critical_values: Optional[List[str]] = None
    acceptable_behavior: Optional[List[str]] = None
    unacceptable_behavior: Optional[List[str]] = None
    fit_indicators: Optional[List[str]] = None
    misfit_indicators: Optional[List[str]] = None
    software: Optional[List[str]] = None
    tools: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    appearance: Optional[str] = None
    keywords: Optional[List[str]] = None
    similar_positions: Optional[List[str]] = None
    stop_companies: Optional[List[str]] = None
    donor_companies: Optional[List[str]] = None
    referral_sources: Optional[List[str]] = None
    schedule: Optional[str] = None
    work_format: Optional[str] = None
    work_address: Optional[str] = Field(default=None, max_length=500)
    background_search: Optional[bool] = None
    work_day_description: Optional[str] = None
    business_trips_required: Optional[bool] = None
    business_trips_frequency: Optional[str] = None
    business_trips_locations: Optional[str] = None
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    currency: Optional[str] = None
    gross: Optional[bool] = None
    bonus_type: Optional[str] = None
    bonus_amount: Optional[str] = None
    bonus_conditions: Optional[str] = None
    benefits: Optional[List[str]] = None
    test_required: Optional[bool] = None
    test_description: Optional[str] = None
    test_deadline: Optional[str] = None
    test_is_paid: Optional[bool] = None
    planned_close_date: Optional[date] = None
    initiator_name: Optional[str] = None
    assigned_hr_id: Optional[str] = Field(default=None, max_length=36)
    assigned_hr_name: Optional[str] = Field(default=None, max_length=200)


class HiringRequestStatusChange(BaseModel):
    status: HiringRequestStatus
    comment: Optional[str] = Field(default=None, max_length=4000)
    reason: Optional[str] = Field(default=None, max_length=4000)


class HiringRequestHistoryRead(BaseModel):
    id: int
    event_type: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    comment: Optional[str] = None
    changes: Optional[dict] = None
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EmployeeRequestRead(EmployeeRequestBase):
    id: int
    created_at: datetime
    updated_at: datetime
    status_changed_at: Optional[datetime] = None
    days_in_status: Optional[int] = None
    public_code: Optional[str] = None
    deadline_state: Optional[str] = None
    assigned_hr_id: Optional[str] = None
    assigned_hr_name: Optional[str] = None
    return_comment: Optional[str] = None
    close_reason: Optional[str] = None
    cancel_reason: Optional[str] = None

    class Config:
        from_attributes = True
