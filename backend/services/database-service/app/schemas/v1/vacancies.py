from typing import Optional, List
from datetime import datetime, date

from pydantic import BaseModel, Field, EmailStr, model_validator

from app.db.v1.enums import Departments, WorkExpirience, Gender, UpdateDate
from app.utils.tz_helpers import deadline_state, vacancy_public_code


class BaseVacancy(BaseModel):
    name: str = Field(..., example='Логист')
    billing_type_id: Optional[str] = Field(default=None, example='standard')
    vacancy_type_id: str = Field(..., example='open')
    synonyms: list[str] = Field(..., example=['Специалист по логистике', 'Инженер логистики'])
    description: Optional[str] = Field(None, min_length=200, example='Описание вакансии логиста...' + ('x' * 180))
    department: Departments = Field(..., example=Departments.logistics.value)
    area_id: Optional[str] = Field(default=None, example='14')
    schedule_id: Optional[str] = Field(default=None, example='fullDay')
    employment_id: Optional[str] = Field(default=None, example='full')
    professional_roles_id: Optional[list[str]] = Field(default=None, example=['67'])
    hh_vacancy_id: Optional[str] = Field(default=None, example='1234567')
    hh_vacancy_url: Optional[str] = Field(default=None, example='https://hh.ru/vacancy/1234567')
    age: Optional[int] = Field(default=None, example=35)
    gender: Optional[Gender] = Field(default=None, example=Gender.male.value)
    languages: Optional[list[str]] = Field(default=None, example=['Английский'])
    personal_characteristics: Optional[str] = Field(default=None, example='Целеустремленный, продуктивный')
    relevant_position_expirience: Optional[str] = Field(default=None, example='работа кем то типо логиста от 2 лет')
    certain_position_expirience: Optional[str] = Field(default=None, example='работа логистом минимум 3 года')
    total_work_expirience: Optional[WorkExpirience] = Field(default=None, example=WorkExpirience.no_experience.value)
    other_work_expirience: Optional[list[str]] = Field(default=None, example=['Водитель от 3 лет'])
    average_service_length: Optional[float] = Field(default=None, description='in years', example=1.2)
    education: Optional[list[str]] = Field(default=None, example=['Среднее профессиональное любое', 'сертификат логиста'])
    required_hard_skills: Optional[list[str]] = Field(default=None, example=['Python', 'C1'])
    optional_hard_skills: Optional[list[str]] = Field(default=None, example=['Ведение бухгалтерии'])
    main_tasks: Optional[list[str]] = Field(default=None, example=['Делать свою логистическую работу'])
    secondary_tasks: Optional[list[str]] = Field(default=None, example=['пить чай и кофе'])
    work_programs: Optional[list[str]] = Field(default=None, example=['excel'])
    kpi_metrics: Optional[list[str]] = Field(default=None, example=['количество выпитых чашек кофе'])
    resume_update_date: Optional[UpdateDate] = Field(default=None, example=UpdateDate.month.value)
    active_search: Optional[bool] = Field(default=None, example=True)
    salary_from: Optional[int] = Field(default=None, example=30000)
    salary_to: Optional[int] = Field(default=None, example=50000)
    currency_id: Optional[str] = Field(default=None, example='RUR')
    gross: Optional[bool] = Field(default=None, example=True)
    work_address: Optional[str] = Field(default=None, max_length=500, example="г. Москва, ул. Примерная, 1")
    is_internal_hidden: bool = Field(default=False, description="Скрыть из рабочего списка, не меняя HH")
    planned_close_date: Optional[date] = Field(default=None, example='2026-09-01')
    is_template: Optional[bool] = Field(default=False, example=False)
    hiring_request_id: Optional[int] = Field(default=None, example=1)
    filter_id: Optional[int] = Field(default=None, example=1, description="Связанный VacancyFilter")


class CreateVacancy(BaseVacancy):
    pass


class VacancyUpdate(BaseModel):
    name: Optional[str] = None
    billing_type_id: Optional[str] = None
    description: Optional[str] = None
    vacancy_type_id: Optional[str] = None
    synonyms: Optional[list[str]] = None
    department: Optional[Departments] = None
    area_id: Optional[str] = None
    schedule_id: Optional[str] = None
    employment_id: Optional[str] = None
    professional_roles_id: Optional[list[str]] = None
    hh_vacancy_id: Optional[str] = None
    hh_vacancy_url: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[Gender] = None
    languages: Optional[list[str]] = None
    personal_characteristics: Optional[str] = None
    relevant_position_expirience: Optional[str] = None
    certain_position_expirience: Optional[str] = None
    total_work_expirience: Optional[WorkExpirience] = None
    other_work_expirience: Optional[list[str]] = None
    average_service_length: Optional[float] = None
    education: Optional[list[str]] = None
    required_hard_skills: Optional[list[str]] = None
    optional_hard_skills: Optional[list[str]] = None
    main_tasks: Optional[list[str]] = None
    secondary_tasks: Optional[list[str]] = None
    work_programs: Optional[list[str]] = None
    kpi_metrics: Optional[list[str]] = None
    resume_update_date: Optional[UpdateDate] = None
    active_search: Optional[bool] = None
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    currency_id: Optional[str] = None
    gross: Optional[bool] = None
    work_address: Optional[str] = Field(default=None, max_length=500)
    is_internal_hidden: Optional[bool] = None
    planned_close_date: Optional[date] = None
    is_template: Optional[bool] = None
    hiring_request_id: Optional[int] = None
    filter_id: Optional[int] = None


class VacancyOption(BaseModel):
    """Lightweight vacancy row for filters / selects (no description payload)."""
    id: int
    name: str
    hh_vacancy_id: Optional[str] = None
    hh_vacancy_url: Optional[str] = None

    class Config:
        from_attributes = True


class ReadVacancy(BaseVacancy):
    id: int = Field(..., example=1)
    created_at: datetime
    updated_at: datetime
    public_code: Optional[str] = Field(None, example='В-12')
    deadline_state: Optional[str] = Field(None, example='warning')
    # Set only by PATCH when an HH push was attempted (not persisted)
    hh_synced: Optional[bool] = Field(default=None, example=True)
    hh_sync_error: Optional[str] = Field(default=None, example=None)

    class Config:
        from_attributes = True

    @model_validator(mode='wrap')
    @classmethod
    def _enrich(cls, values, handler):
        obj = handler(values)
        if getattr(obj, 'public_code', None) is None and getattr(obj, 'id', None) is not None:
            obj.public_code = vacancy_public_code(obj.id)
        if getattr(obj, 'deadline_state', None) is None:
            obj.deadline_state = deadline_state(getattr(obj, 'planned_close_date', None))
        return obj


class TestsForVacancy(BaseModel):
    test_ids: list[int] = Field(..., example=[1])


class VacancyFilters(BaseModel):
    department: Optional[Departments] = Field(default=None, example=Departments.logistics.value)
    employment_id: Optional[str] = Field(default=None, example='full')
    salary_from: Optional[int] = Field(default=None, example=30000)
    salary_to: Optional[int] = Field(default=None, example=50000)


#========================
#      HH MAPPING
#========================
class Area(BaseModel):
    id: str = Field(..., description="ID региона публикации (например, '1' — Москва)")


class Salary(BaseModel):
    from_: Optional[int] = Field(None, alias="from", description="Минимальная зарплата")
    to: Optional[int] = Field(None, description="Максимальная зарплата")
    currency: Optional[str] = Field("RUR", description="Валюта: 'RUR', 'USD' и т. д.")
    gross: Optional[bool] = Field(False, description="True — до вычета налогов, False — на руки")

    class Config:
        populate_by_name = True


class IDRef(BaseModel):
    id: str = Field(..., description="Идентификатор справочного значения")


class Phone(BaseModel):
    country: str = Field(..., description="Код страны (например, '7')")
    city: str = Field(..., description="Код города (например, '495')")
    number: str = Field(..., description="Основной номер телефона без +7 и кода города")


class Contacts(BaseModel):
    name: str = Field(..., description="Имя контактного лица")
    email: Optional[EmailStr] = Field(None, description="Email для связи")
    phones: List[Phone] = Field(default_factory=list, description="Список телефонов")


class VacancyPropertyItem(BaseModel):
    property_type: str = Field(default="HH_STANDARD", description="Тип публикации на HH")


class VacancyProperties(BaseModel):
    properties: List[VacancyPropertyItem] = Field(
        default_factory=lambda: [VacancyPropertyItem(property_type="HH_STANDARD")]
    )


class VacancyPostSchema(BaseModel):
    name: str = Field(..., description="Название вакансии")
    area: Area
    salary: Optional[Salary] = None
    description: str = Field(..., min_length=200, description="Описание вакансии (>=200 символов)")
    employment: IDRef
    schedule: IDRef
    experience: IDRef
    professional_roles: List[IDRef]
    vacancy_properties: VacancyProperties = Field(default_factory=VacancyProperties)
    type: IDRef
    billing_type: IDRef
    contacts: Contacts

    class Config:
        extra = "ignore"
        populate_by_name = True
        schema_extra = {
            "example": {
                "name": "Дворник",
                "area": {"id": "1"},
                "salary": {"from": 23000, "to": 23000, "currency": "RUR", "gross": False},
                "description": "Длинное описание (200+ символов)..." + ("x" * 160),
                "employment": {"id": "full"},
                "schedule": {"id": "fullDay"},
                "experience": {"id": "noExperience"},
                "professional_roles": [{"id": "10"}],
                "vacancy_properties": {"properties": [{"property_type": "HH_STANDARD"}]},
                "type": {"id": "open"},
                "billing_type": {"id": "standard"},
                "contacts": {
                    "name": "Иван Иванов",
                    "email": "test@example.com",
                    "phones": [{"country": "7", "city": "495", "number": "1234567"}]
                }
            }
        }
