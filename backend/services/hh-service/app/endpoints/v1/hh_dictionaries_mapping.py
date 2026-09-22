from fastapi import APIRouter, HTTPException, Query
from app.clients.hh.hh_dictionaries import HHDictionaries

router = APIRouter()
dicts = HHDictionaries()


# --- Универсальный helper ---
def not_found_error(entity: str, entity_id: str):
    raise HTTPException(status_code=404, detail=f"{entity} with id '{entity_id}' not found")


# --- Мапперы по id ---
@router.get("/areas/{area_id}")
def get_area_name(area_id: str):
    """Получить название региона по его ID (area_id)."""
    name = dicts.get_area_name(area_id)
    if not name:
        not_found_error("Area", area_id)
    return {"id": area_id, "name": name}


@router.get("/professional_roles/{role_id}")
def get_professional_role_name(role_id: str):
    """Получить название профессиональной роли по ID."""
    name = dicts.get_professional_role_name(role_id)
    if not name:
        not_found_error("Professional role", role_id)
    return {"id": role_id, "name": name}


@router.get("/currency/{currency_id}")
def get_currency_name(currency_id: str):
    """Получить название валюты по ID ('RUR', 'USD', и т.д.)."""
    name = dicts.get_currency_name(currency_id)
    if not name:
        not_found_error("Currency", currency_id)
    return {"id": currency_id, "name": name}


@router.get("/experience/{exp_id}")
def get_experience_name(exp_id: str):
    """Получить название уровня опыта по ID ('noExperience', 'between1And3', ...)."""
    name = dicts.get_experience_name(exp_id)
    if not name:
        not_found_error("Experience", exp_id)
    return {"id": exp_id, "name": name}


@router.get("/employment/{emp_id}")
def get_employment_name(emp_id: str):
    """Получить тип занятости по ID ('full', 'part', и т.д.)."""
    name = dicts.get_employment_name(emp_id)
    if not name:
        not_found_error("Employment", emp_id)
    return {"id": emp_id, "name": name}


@router.get("/schedule/{sched_id}")
def get_schedule_name(sched_id: str):
    """Получить график работы по ID ('remote', 'flexible', и т.д.)."""
    name = dicts.get_schedule_name(sched_id)
    if not name:
        not_found_error("Schedule", sched_id)
    return {"id": sched_id, "name": name}


@router.get("/work_format/{wf_id}")
def get_work_format_name(wf_id: str):
    """Получить формат работы по ID (ON_SITE, REMOTE и т.д.)."""
    name = dicts.get_work_format_name(wf_id)
    if not name:
        not_found_error("Work format", wf_id)
    return {"id": wf_id, "name": name}


@router.get("/vacancy_type/{vt_id}")
def get_vacancy_type_name(vt_id: str):
    """Получить тип вакансии по ID ('open', 'anonymous', ...)."""
    name = dicts.get_vacancy_type_name(vt_id)
    if not name:
        not_found_error("Vacancy type", vt_id)
    return {"id": vt_id, "name": name}


@router.get("/billing_type/{bt_id}")
def get_billing_type_name(bt_id: str):
    """Получить тип биллинга по ID ('standard', 'premium', ...)."""
    name = dicts.get_billing_type_name(bt_id)
    if not name:
        not_found_error("Billing type", bt_id)
    return {"id": bt_id, "name": name}


@router.get("/gender/{gender_id}")
def get_gender_name(gender_id: str):
    """Получить название пола по ID ('male', 'female', ...)."""
    name = dicts.get_gender_name(gender_id)
    if not name:
        not_found_error("Gender", gender_id)
    return {"id": gender_id, "name": name}


@router.get("/education_level/{edu_id}")
def get_education_level_name(edu_id: str):
    """Получить уровень образования по ID."""
    name = dicts.get_education_level_name(edu_id)
    if not name:
        not_found_error("Education level", edu_id)
    return {"id": edu_id, "name": name}