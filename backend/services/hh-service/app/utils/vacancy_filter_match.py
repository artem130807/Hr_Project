"""Match HH resume payloads against VacancyFilter criteria."""
from __future__ import annotations

from typing import Any, Optional

from app.utils.resume_parsing import map_months_to_work_experience

EXPERIENCE_ORDER = {
    "noExperience": 0,
    "between1And3": 1,
    "between3And6": 2,
    "moreThan6": 3,
}

# Platform WorkFormat → HH dictionary id
_WORK_FORMAT_TO_HH = {
    "remote": "REMOTE",
    "office": "ON_SITE",
    "hybrid": "HYBRID",
    "field": "FIELD_WORK",
    # no direct HH id for shift
    "shift": None,
}


def map_hh_work_format(platform_value: Optional[str]) -> Optional[str]:
    if not platform_value:
        return None
    return _WORK_FORMAT_TO_HH.get(str(platform_value))


def extract_resume_city(resume: dict) -> Optional[str]:
    area = resume.get("area") if isinstance(resume, dict) else None
    if isinstance(area, dict):
        name = area.get("name")
        return str(name).strip() if name else None
    if isinstance(area, str) and area.strip():
        return area.strip()
    return None


def extract_resume_age(resume: dict) -> Optional[int]:
    age = resume.get("age") if isinstance(resume, dict) else None
    if isinstance(age, int):
        return age
    if isinstance(age, str) and age.isdigit():
        return int(age)
    return None


def extract_resume_experience(resume: dict) -> Optional[str]:
    total = resume.get("total_experience") if isinstance(resume, dict) else None
    months = None
    if isinstance(total, dict):
        months = total.get("months")
    elif isinstance(total, int):
        months = total
    if not isinstance(months, int):
        return None
    exp = map_months_to_work_experience(months)
    return exp.value if exp is not None else None


def extract_resume_work_formats(resume: dict) -> set[str]:
    raw = resume.get("work_format") if isinstance(resume, dict) else None
    ids: set[str] = set()
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("id"):
                ids.add(str(item["id"]))
            elif isinstance(item, str):
                ids.add(item)
    return ids


def _norm_city(value: str) -> str:
    return " ".join(value.casefold().split())


def _experience_meets_minimum(candidate: Optional[str], required: Optional[str]) -> bool:
    if not required:
        return True
    if not candidate:
        return False
    c = EXPERIENCE_ORDER.get(str(candidate))
    r = EXPERIENCE_ORDER.get(str(required))
    if c is None or r is None:
        return str(candidate) == str(required)
    return c >= r


def resolve_hh_filter_action(vacancy_filter: Optional[dict]) -> str:
    """HH action encoded on VacancyFilter.action."""
    raw = str((vacancy_filter or {}).get("action") or "discard").strip().lower()
    if raw in {"consider", "подумать", "think"}:
        return "consider"
    return "discard"


def matches_vacancy_filter(resume: Optional[dict], vacancy_filter: Optional[dict]) -> bool:
    """
    Return True if resume satisfies all set VacancyFilter fields.
    Empty / missing filter → always True (nothing to reject on).
    """
    if not vacancy_filter:
        return True
    if not isinstance(resume, dict):
        return False

    city = vacancy_filter.get("city")
    if city:
        resume_city = extract_resume_city(resume)
        if not resume_city:
            return False
        # allow either-side containment (e.g. "Москва" vs "г. Москва")
        rc, fc = _norm_city(resume_city), _norm_city(str(city))
        if fc not in rc and rc not in fc:
            return False

    age_from = vacancy_filter.get("age_from")
    age_to = vacancy_filter.get("age_to")
    if age_from is not None or age_to is not None:
        age = extract_resume_age(resume)
        if age is None:
            return False
        if age_from is not None and age < int(age_from):
            return False
        if age_to is not None and age > int(age_to):
            return False

    experience = vacancy_filter.get("experience")
    if experience:
        if not _experience_meets_minimum(extract_resume_experience(resume), str(experience)):
            return False

    work_format = vacancy_filter.get("work_format")
    if work_format:
        hh_id = map_hh_work_format(str(work_format))
        if hh_id:
            formats = extract_resume_work_formats(resume)
            if hh_id not in formats:
                return False

    return True


def resume_has_filter_fields(resume: Any) -> bool:
    """True if embedded resume looks complete enough to evaluate without GET /resumes/{id}."""
    if not isinstance(resume, dict) or not resume.get("id"):
        return False
    # need at least one evaluable signal OR empty id alone is not enough when filter is strict —
    # treat as full enough when age or area or total_experience present
    return any(
        key in resume and resume.get(key) is not None
        for key in ("age", "area", "total_experience", "work_format")
    )


def is_unviewed_negotiation(item: dict) -> bool:
    """HH 'непросмотренные' / unsorted responses for employer."""
    if not isinstance(item, dict):
        return False
    if item.get("has_updates"):
        return True
    viewed = item.get("viewed_by_opponent")
    if viewed is True:
        return False
    if viewed is False:
        return True
    employer_state = item.get("employer_state")
    if isinstance(employer_state, dict):
        return employer_state.get("id") == "response"
    return employer_state == "response"
