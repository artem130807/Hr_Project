from fastapi import APIRouter
from typing import List

from app.clients.hh.hh_dictionaries import HHDictionaries
from app.schemas.v1.dictionaries import (
    Area,
    ProfessionalRolesResponse,
    Language,
    Currency,
    ExperienceItem,
    EmploymentItem,
    ScheduleItem,
    EducationLevelItem,
    LanguageLevelItem,
    DriverLicenseTypeItem,
    WorkFormatItem,
    WorkingDaysItem,
    WorkingTimeIntervalsItem,
    WorkingTimeModesItem,
    WorkScheduleByDaysItem,
    WorkingHoursItem,
    AgeRestrictionItem,
    VacancyTypeItem,
)

router = APIRouter()
dicts = HHDictionaries()


# --- Отдельные справочники ---
@router.get("/areas", response_model=List[Area])
def get_areas():
    """Дерево регионов (area) — как в hh.ru."""
    return dicts.get_areas()


@router.get("/professional_roles", response_model=ProfessionalRolesResponse)
def get_professional_roles():
    """Профессиональные роли (группы + роли) — как в hh.ru."""
    return dicts.get_professional_roles()


@router.get('/billing_type')
def get_billing_type():
    """Типы биллинга вакансий."""
    return dicts.get_billing_type()


# @router.get("/languages", response_model=List[Language])
# def get_languages():
#     """Список языков (не уровней!) — как в hh.ru."""
#     return dicts.get_languages()


@router.get("/currency", response_model=List[Currency])
def get_currency():
    """Список валют — как в hh.ru."""
    return dicts.get_currency()


# --- Справочники из /dictionaries ---
@router.get("/employment", response_model=List[EmploymentItem])
def get_employment():
    """Тип занятости."""
    return dicts.get_employment()


@router.get("/schedule", response_model=List[ScheduleItem])
def get_schedule():
    """График работы."""
    return dicts.get_schedule()


@router.get("/experience", response_model=List[ExperienceItem])
def get_experience():
    """Требуемый опыт."""
    return dicts.get_experience()


# @router.get("/education_level", response_model=List[EducationLevelItem])
# def get_education_level():
#     """Уровень образования."""
#     return dicts.get_education_level()


# @router.get("/language_level", response_model=List[LanguageLevelItem])
# def get_language_level():
#     """Уровень владения языком."""
#     return dicts.get_language_level()


# @router.get("/driver_license_types", response_model=List[DriverLicenseTypeItem])
# def get_driver_license_types():
#     """Категории водительских прав."""
#     return dicts.get_driver_license_types()


@router.get("/work_format", response_model=List[WorkFormatItem])
def get_work_format():
    """Формат работы (ON_SITE, REMOTE и т.д.)."""
    return dicts.get_work_format()


# @router.get("/working_days", response_model=List[WorkingDaysItem])
# def get_working_days():
#     """Рабочие дни."""
#     return dicts.get_working_days()


# @router.get("/working_time_intervals", response_model=List[WorkingTimeIntervalsItem])
# def get_working_time_intervals():
#     """Продолжительность смены."""
#     return dicts.get_working_time_intervals()


# @router.get("/working_time_modes", response_model=List[WorkingTimeModesItem])
# def get_working_time_modes():
#     """Время начала работы."""
#     return dicts.get_working_time_modes()


# @router.get("/work_schedule_by_days", response_model=List[WorkScheduleByDaysItem])
# def get_work_schedule_by_days():
#     """Схема чередования дней (5/2, 2/2 и т.п.)."""
#     return dicts.get_work_schedule_by_days()


# @router.get("/working_hours", response_model=List[WorkingHoursItem])
# def get_working_hours():
#     """Количество часов в день."""
#     return dicts.get_working_hours()


# @router.get("/age_restriction", response_model=List[AgeRestrictionItem])
# def get_age_restriction():
#     """Возрастные ограничения."""
#     return dicts.get_age_restriction()


@router.get("/vacancy_type", response_model=List[VacancyTypeItem])
def get_vacancy_type():
    """Тип вакансии."""
    return dicts.get_vacancy_type()


# # --- Дополнительные справочники из /dictionaries ---

@router.get("/skills")
def get_skills():
    """Навыки (skills)."""
    return dicts.get_skills()


# @router.get("/resume_access_type")
# def get_resume_access_type():
#     """Типы доступа к резюме."""
#     return dicts.get_resume_access_type()


# @router.get("/vacancy_search_order")
# def get_vacancy_search_order():
#     """Порядок сортировки вакансий."""
#     return dicts.get_vacancy_search_order()


# @router.get("/vacancy_search_fields")
# def get_vacancy_search_fields():
#     """Поля поиска вакансий."""
#     return dicts.get_vacancy_search_fields()


@router.get("/gender")
def get_gender():
    """Пол кандидата."""
    return dicts.get_gender()


# @router.get("/preferred_contact_type")
# def get_preferred_contact_type():
#     """Предпочтительный способ связи."""
#     return dicts.get_preferred_contact_type()


# @router.get("/travel_time")
# def get_travel_time():
#     """Время в пути до работы."""
#     return dicts.get_travel_time()


# @router.get("/relocation_type")
# def get_relocation_type():
#     """Тип переезда."""
#     return dicts.get_relocation_type()


# @router.get("/business_trip_readiness")
# def get_business_trip_readiness():
#     """Готовность к командировкам."""
#     return dicts.get_business_trip_readiness()


# @router.get("/salary_range_mode")
# def get_salary_range_mode():
#     """Режим указания зарплаты (gross/net)."""
#     return dicts.get_salary_range_mode()


# @router.get("/salary_range_frequency")
# def get_salary_range_frequency():
#     """Частота выплат (ежемесячно, ежегодно и т.д.)."""
#     return dicts.get_salary_range_frequency()


# @router.get("/fly_in_fly_out_duration")
# def get_fly_in_fly_out_duration():
#     """Продолжительность вахты."""
#     return dicts.get_fly_in_fly_out_duration()


# @router.get("/employment_form")
# def get_employment_form():
#     """Форма занятости."""
#     return dicts.get_employment_form()


# @router.get("/resume_status")
# def get_resume_status():
#     """Статусы резюме."""
#     return dicts.get_resume_status()


# @router.get("/messaging_status")
# def get_messaging_status():
#     """Статусы переписки."""
#     return dicts.get_messaging_status()


# @router.get("/vacancy_relation")
# def get_vacancy_relation():
#     """Связи вакансий."""
#     return dicts.get_vacancy_relation()


# @router.get("/resume_hidden_fields")
# def get_resume_hidden_fields():
#     """Скрытые поля резюме."""
#     return dicts.get_resume_hidden_fields()


# @router.get("/vacancy_label")
# def get_vacancy_label():
#     """Метки вакансий."""
#     return dicts.get_vacancy_label()


# @router.get("/employer_type")
# def get_employer_type():
#     """Тип работодателя."""
#     return dicts.get_employer_type()


# @router.get("/resume_contacts_site_type")
# def get_resume_contacts_site_type():
#     """Тип сайта для контактов в резюме."""
#     return dicts.get_resume_contacts_site_type()


# @router.get("/job_search_statuses_applicant")
# def get_job_search_statuses_applicant():
#     """Статусы поиска работы (соискатель)."""
#     return dicts.get_job_search_statuses_applicant()


# @router.get("/job_search_statuses_employer")
# def get_job_search_statuses_employer():
#     """Статусы поиска работы (работодатель)."""
#     return dicts.get_job_search_statuses_employer()
