"""Map hiring request → local Vacancy payload and hire → Employee."""
from __future__ import annotations

from datetime import date
from typing import Any

from app.db.v1.enums import CandidateStage, Gender, MaritalStatus
from app.db.v1.models import Candidate, Employee, EmployeeRequest, Vacancy


def _join_parts(*parts: str | None, sep: str = "\n\n") -> str:
    cleaned = [p.strip() for p in parts if p and str(p).strip()]
    return sep.join(cleaned)


def build_description_from_request(req: EmployeeRequest) -> str:
    blocks = [
        req.purpose,
        f"Особенности: {req.features}" if req.features else None,
        f"Подчинение: {req.reporting}" if req.reporting else None,
    ]
    if req.mandatory_requirements:
        blocks.append("Обязательные требования:\n- " + "\n- ".join(req.mandatory_requirements))
    if req.desired_requirements:
        blocks.append("Желательные требования:\n- " + "\n- ".join(req.desired_requirements))
    if req.daily_tasks:
        blocks.append("Ежедневные задачи:\n- " + "\n- ".join(req.daily_tasks))
    if req.required_hard_skills:
        blocks.append("Hard skills: " + ", ".join(req.required_hard_skills))
    if req.work_day_description:
        blocks.append(req.work_day_description)

    text = _join_parts(*blocks) or f"Вакансия: {req.position}. Отдел: {req.department}."
    # HH requires >= 200 chars
    if len(text) < 200:
        pad = (
            f"\n\nПозиция «{req.position}» в отделе «{req.department}». "
            "Описание сформировано из заявки на подбор; дополните детали перед публикацией на HH.ru. "
        )
        while len(text) < 200:
            text += pad
        text = text[: max(200, len(text))]
    return text


def vacancy_hh_publish_gaps(vacancy: Vacancy | None) -> list[str]:
    """Fields required by map-to-hh that are often missing after create-from-request."""
    if vacancy is None:
        return ["вакансия не найдена"]
    gaps: list[str] = []
    roles = [r for r in (vacancy.professional_roles_id or []) if r]
    if not roles:
        gaps.append("профессиональная роль (professional_roles_id)")
    if not vacancy.area_id:
        gaps.append("город / area_id")
    desc = (vacancy.description or "").strip()
    if len(desc) < 200:
        gaps.append("описание ≥ 200 символов")
    return gaps


def vacancy_payload_from_request(req: EmployeeRequest) -> dict[str, Any]:
    synonyms = list(req.similar_positions or []) or list(req.keywords or []) or [req.position]
    return {
        "name": req.position,
        "vacancy_type_id": "open",
        "billing_type_id": "standard",
        # Empty until HR picks HH dictionaries in VacancyForm — required non-null JSON column
        "professional_roles_id": [],
        "schedule_id": "fullDay",
        "employment_id": "full",
        "area_id": None,
        "synonyms": synonyms,
        "department": req.department,
        "description": build_description_from_request(req),
        "required_hard_skills": list(req.required_hard_skills or []),
        "optional_hard_skills": list(req.optional_hard_skills or []),
        "main_tasks": list(req.daily_tasks or []),
        "secondary_tasks": list(req.weekly_tasks or []),
        "kpi_metrics": list(req.kpi_metrics or []),
        "work_programs": list(req.software or []),
        "languages": list(req.languages or []),
        "salary_from": req.salary_from or 0,
        "salary_to": req.salary_to or 0,
        "currency_id": "RUR" if (req.currency or "").upper() in ("", "RUB", "RUR") else req.currency,
        "gross": req.gross if req.gross is not None else True,
        "work_address": req.work_address,
        "is_internal_hidden": False,
        "active_search": True,
        "is_template": False,
        "hiring_request_id": req.id,
        "planned_close_date": req.planned_close_date,
        "age": req.age_from,
        "personal_characteristics": ", ".join(req.required_soft_skills or []) or None,
    }


def employee_from_candidate(
    candidate: Candidate,
    *,
    vacancy: Vacancy | None = None,
) -> Employee:
    """Build Employee ORM object from hired candidate (not yet added to session)."""
    raw_dept = getattr(vacancy, "department", None) if vacancy is not None else None
    if raw_dept is None:
        dept = "hr"
    else:
        dept = str(getattr(raw_dept, "value", raw_dept))
    position = (vacancy.name if vacancy else None) or "Сотрудник"
    phone = (candidate.phone_number or "").strip() or None
    if phone and len(phone) > 20:
        phone = phone[:20]

    gender = candidate.gender
    if gender is not None and not isinstance(gender, Gender):
        try:
            gender = Gender(gender)
        except Exception:
            gender = None

    marital = candidate.marital_status
    if marital is not None and not isinstance(marital, MaritalStatus):
        try:
            marital = MaritalStatus(marital)
        except Exception:
            marital = None

    return Employee(
        user_id=candidate.user_id,
        candidate_id=candidate.id,
        full_name=candidate.full_name or f"Кандидат #{candidate.id}",
        gender=gender,
        phone_number=phone,
        department=str(dept),
        position=position,
        marital_status=marital,
        hobbies=list(candidate.hobbies or []) if candidate.hobbies else [],
        personal_characteristics=candidate.personal_characteristics or "",
        birth_date=candidate.birth_date,
        age=candidate.age,
        service_length=0,
        date_hired=date.today(),
    )


def stage_value(stage: Any) -> str | None:
    if stage is None:
        return None
    return str(getattr(stage, "value", stage))
