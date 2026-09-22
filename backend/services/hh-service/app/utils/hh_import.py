"""Helpers to normalize HH employer vacancies and negotiation (отклики) lists."""
from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from app.clients.hh.simple_hh_client import SimpleHHClient
from app.app_logging import logger
from app.utils.resume_parsing import extract_hh_resume_contacts, format_hh_full_name, safe_get, safe_str

# Must match database-service Departments enum values.
LOCAL_DEPARTMENTS = frozenset(
    {
        "hr",
        "логистический",
        "делопроизводственный",
        "юридический",
        "бухгалтерия",
        "art",
        "IT",
        "развитие",
    }
)

_HH_EXPERIENCE = frozenset(
    {"noExperience", "between1And3", "between3And6", "moreThan6"}
)


def _strip_html(text: str | None) -> str:
    raw = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", raw).strip()


def build_local_vacancy_from_hh(hh_vac: dict, department: str) -> dict:
    """Map full HH vacancy payload → CreateVacancy body for database-service."""
    if not isinstance(hh_vac, dict):
        raise HTTPException(502, "HH vacancy payload is empty")

    dept = (department or "").strip()
    if dept.lower() == "it":
        dept = "IT"
    if dept not in LOCAL_DEPARTMENTS:
        raise HTTPException(
            400,
            f"Неизвестный отдел «{department}». Допустимо: {', '.join(sorted(LOCAL_DEPARTMENTS))}",
        )

    hh_id = hh_vac.get("id")
    if hh_id is None:
        raise HTTPException(502, "HH vacancy has no id")

    name = (hh_vac.get("name") or "").strip() or f"Вакансия HH {hh_id}"
    vtype = hh_vac.get("type") if isinstance(hh_vac.get("type"), dict) else {}
    area = hh_vac.get("area") if isinstance(hh_vac.get("area"), dict) else {}
    salary = hh_vac.get("salary") if isinstance(hh_vac.get("salary"), dict) else {}
    schedule = hh_vac.get("schedule") if isinstance(hh_vac.get("schedule"), dict) else {}
    employment = (
        hh_vac.get("employment") if isinstance(hh_vac.get("employment"), dict) else {}
    )
    experience = (
        hh_vac.get("experience") if isinstance(hh_vac.get("experience"), dict) else {}
    )

    roles: list[str] = []
    for role in hh_vac.get("professional_roles") or []:
        if isinstance(role, dict) and role.get("id") is not None:
            roles.append(str(role["id"]))

    skills: list[str] = []
    for skill in hh_vac.get("key_skills") or []:
        if isinstance(skill, dict) and skill.get("name"):
            skills.append(str(skill["name"]).strip())
        elif isinstance(skill, str) and skill.strip():
            skills.append(skill.strip())

    description = _strip_html(hh_vac.get("description"))
    # CreateVacancy: description optional, but if set must be ≥ 200 chars
    if len(description) < 200:
        description = None

    exp_id = experience.get("id")
    total_exp = exp_id if exp_id in _HH_EXPERIENCE else None

    url = hh_vac.get("alternate_url") or f"https://hh.ru/vacancy/{hh_id}"

    payload: dict[str, Any] = {
        "name": name,
        "vacancy_type_id": vtype.get("id") or "open",
        "synonyms": [name],
        "department": dept,
        "description": description,
        "area_id": str(area["id"]) if area.get("id") is not None else None,
        "schedule_id": schedule.get("id"),
        "employment_id": employment.get("id"),
        "professional_roles_id": roles or None,
        "required_hard_skills": skills or None,
        "total_work_expirience": total_exp,
        "salary_from": salary.get("from"),
        "salary_to": salary.get("to"),
        "currency_id": salary.get("currency"),
        "gross": salary.get("gross"),
        "hh_vacancy_id": str(hh_id),
        "hh_vacancy_url": url,
        "is_template": False,
    }
    return {k: v for k, v in payload.items() if v is not None}


def _resume_filter_fields(resume: dict) -> dict:
    """Fields needed to filter a negotiation list row (city / age / experience / work format)."""
    area = resume.get("area")
    area_name = area.get("name") if isinstance(area, dict) else (area if isinstance(area, str) else None)
    total_exp = resume.get("total_experience") or {}
    months = total_exp.get("months") if isinstance(total_exp, dict) else None
    work_formats: list[dict] = []
    raw_formats = resume.get("work_format") or []
    if isinstance(raw_formats, list):
        for item in raw_formats:
            if isinstance(item, dict) and item.get("id"):
                work_formats.append({"id": str(item["id"]), "name": item.get("name")})
            elif isinstance(item, str) and item.strip():
                work_formats.append({"id": item.strip(), "name": None})
    return {
        "area": safe_str(area_name),
        "experience_months": months if isinstance(months, int) else None,
        "work_formats": work_formats,
    }


def _resume_summary(resume: Any) -> dict | None:
    if not isinstance(resume, dict):
        return None
    return {
        "id": resume.get("id"),
        "title": resume.get("title"),
        "full_name": format_hh_full_name(resume=resume),
        "first_name": resume.get("first_name"),
        "last_name": resume.get("last_name"),
        "middle_name": resume.get("middle_name"),
        "age": resume.get("age"),
        "alternate_url": resume.get("alternate_url"),
        "url": resume.get("url") or resume.get("download") or None,
        **_resume_filter_fields(resume),
    }


def _dict_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return safe_str(value.get("name"))
    return safe_str(value)


def _photo_url(resume: dict) -> str | None:
    photo = resume.get("photo")
    if isinstance(photo, str) and photo.startswith("http"):
        return photo
    if not isinstance(photo, dict):
        return None
    for key in ("medium", "small", "500", "100", "40"):
        val = photo.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
        if isinstance(val, dict):
            url = val.get("url") or val.get("src")
            if isinstance(url, str) and url.startswith("http"):
                return url
    return None


def _resume_experience_jobs(resume: dict) -> list[dict]:
    jobs: list[dict] = []
    experiences = resume.get("experience") or []
    if not isinstance(experiences, list):
        return jobs
    for exp in experiences:
        if not isinstance(exp, dict):
            continue
        industries = exp.get("industries") or []
        industry = None
        if isinstance(industries, list) and industries:
            industry = _dict_name(industries[0])
        elif exp.get("industry"):
            industry = _dict_name(exp.get("industry"))
        start, end = safe_get(exp, "start"), safe_get(exp, "end")
        period = None
        if start or end:
            period = f"{start or '?'} — {end or 'н.в.'}"
        jobs.append(
            {
                "title": safe_get(exp, "position"),
                "company": safe_get(exp, "company"),
                "period": period,
                "industry": industry,
                "region": _dict_name(exp.get("area")),
                "description": safe_get(exp, "description"),
            }
        )
    return jobs


def _resume_education(resume: dict) -> list[str]:
    education_list: list[str] = []
    education = resume.get("education") or {}
    if isinstance(education, dict):
        for v in education.values():
            if isinstance(v, list):
                for e in v:
                    if isinstance(e, dict):
                        val = safe_get(e, "name") or safe_get(e, "organization") or safe_get(e, "result")
                        if val:
                            education_list.append(val)
                    elif e:
                        education_list.append(str(e))
            elif isinstance(v, str) and v.strip():
                education_list.append(v.strip())
    elif isinstance(education, list):
        education_list.extend([str(x) for x in education if x])
    return education_list


def _resume_languages(resume: dict) -> list[str]:
    out: list[str] = []
    langs = resume.get("language") or []
    if not isinstance(langs, list):
        return out
    for lang in langs:
        if isinstance(lang, dict):
            name = safe_get(lang, "name")
            if not name:
                continue
            level = _dict_name(lang.get("level"))
            out.append(f"{name} — {level}" if level else name)
        elif isinstance(lang, str) and lang.strip():
            out.append(lang.strip())
    return out


def _resume_skill_set(resume: dict) -> list[str]:
    hard_skills: list[str] = []
    skills = resume.get("skill_set") or []
    if not isinstance(skills, list):
        return hard_skills
    for s in skills:
        if isinstance(s, dict):
            name = safe_get(s, "name")
            if name:
                hard_skills.append(name)
        elif isinstance(s, str) and s.strip():
            hard_skills.append(s.strip())
    return hard_skills


def _enrich_resume_card(resume_src: dict, summary: dict) -> dict:
    """Full resume fields for the candidate-style card (no AI — person is not in CRM yet)."""
    area = resume_src.get("area") or {}
    salary = resume_src.get("salary") or {}
    total_exp = resume_src.get("total_experience") or {}
    contacts = extract_hh_resume_contacts(resume_src)
    job_search = resume_src.get("job_search_status")
    job_search_id = job_search.get("id") if isinstance(job_search, dict) else None
    job_search_name = _dict_name(job_search)
    active_search = None
    if isinstance(job_search_id, str):
        active_search = job_search_id in {
            "active_search",
            "looking_for_offers",
            "has_job_offer",
        }
    skills_text = resume_src.get("skills")
    if not isinstance(skills_text, str):
        skills_text = None
    gender = resume_src.get("gender")
    summary.update(
        {
            "area": area.get("name") if isinstance(area, dict) else summary.get("area"),
            "experience_months": total_exp.get("months") if isinstance(total_exp, dict) else None,
            "skill_set": _resume_skill_set(resume_src),
            "salary_amount": salary.get("amount") if isinstance(salary, dict) else None,
            "salary_currency": salary.get("currency") if isinstance(salary, dict) else None,
            "gender": _dict_name(gender) if isinstance(gender, dict) else gender,
            "birth_date": resume_src.get("birth_date"),
            "photo_url": _photo_url(resume_src),
            "phone_number": contacts.phone,
            "email": contacts.email,
            "telegram_username": contacts.telegram,
            "updated_at": resume_src.get("updated_at"),
            "experience": _resume_experience_jobs(resume_src),
            "education": _resume_education(resume_src),
            "languages": _resume_languages(resume_src),
            "about": skills_text.strip() if skills_text else None,
            "job_search_status": job_search_name,
            "active_search": active_search,
            "citizenship": [
                _dict_name(c)
                for c in (resume_src.get("citizenship") or [])
                if _dict_name(c)
            ]
            if isinstance(resume_src.get("citizenship"), list)
            else [],
        }
    )
    return summary


def normalize_vacancy_item(item: dict) -> dict:
    area = item.get("area") or {}
    salary = item.get("salary") or {}
    counters = item.get("counters") if isinstance(item.get("counters"), dict) else {}
    manager = item.get("manager") if isinstance(item.get("manager"), dict) else {}
    vtype = item.get("type") if isinstance(item.get("type"), dict) else None
    return {
        "hh_vacancy_id": str(item.get("id")) if item.get("id") is not None else None,
        "name": item.get("name"),
        "alternate_url": item.get("alternate_url"),
        "published_at": item.get("published_at") or item.get("created_at"),
        "archived": bool(item.get("archived")),
        "premium": bool(item.get("premium")),
        # HH: закрыта для откликов / фактически «скрыта из поиска»
        "closed_for_applicants": bool(item.get("closed_for_applicants")),
        "type_id": vtype.get("id") if isinstance(vtype, dict) else None,
        "type_name": vtype.get("name") if isinstance(vtype, dict) else None,
        "manager_id": str(manager["id"]) if manager.get("id") is not None else None,
        "manager_name": (
            " ".join(
                p for p in (manager.get("last_name"), manager.get("first_name")) if p
            ).strip()
            or None
        ),
        "area": area.get("name") if isinstance(area, dict) else None,
        "salary_from": salary.get("from") if isinstance(salary, dict) else None,
        "salary_to": salary.get("to") if isinstance(salary, dict) else None,
        "currency": salary.get("currency") if isinstance(salary, dict) else None,
        "responses_count": counters.get("responses") if counters else item.get("responses_count"),
    }


def normalize_negotiation_item(item: dict) -> dict:
    resume = _resume_summary(item.get("resume"))
    state = item.get("state") or {}
    employer_state = item.get("employer_state") or {}
    return {
        "id": item.get("id"),
        "chat_id": item.get("chat_id"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "viewed_by_opponent": item.get("viewed_by_opponent"),
        "state": state.get("id") if isinstance(state, dict) else state,
        "state_name": state.get("name") if isinstance(state, dict) else None,
        "employer_state": employer_state.get("id") if isinstance(employer_state, dict) else employer_state,
        "employer_state_name": employer_state.get("name") if isinstance(employer_state, dict) else None,
        "resume": resume,
        "has_updates": item.get("has_updates"),
        "url": item.get("url"),
    }


def _normalize_action(action: dict) -> dict | None:
    if not isinstance(action, dict) or not action.get("id"):
        return None
    args_raw = action.get("arguments") or []
    arguments = []
    for a in args_raw:
        if not isinstance(a, dict) or not a.get("id"):
            continue
        arguments.append(
            {
                "id": a.get("id"),
                "required": bool(a.get("required")),
                "name": a.get("name"),
            }
        )
    resulting = action.get("resulting_employer_state")
    resulting_id = None
    resulting_name = None
    if isinstance(resulting, dict):
        resulting_id = resulting.get("id")
        resulting_name = resulting.get("name")
    return {
        "id": action.get("id"),
        "name": action.get("name") or action.get("id"),
        "enabled": bool(action.get("enabled")),
        "method": (action.get("method") or "PUT").upper(),
        "arguments": arguments,
        "resulting_employer_state": resulting_id,
        "resulting_employer_state_name": resulting_name,
    }


def normalize_negotiation_detail(topic: dict, *, resume: dict | None = None) -> dict:
    """
    Safe DTO for FE: negotiation + resume details + actions without raw HH URLs.
    """
    if not isinstance(topic, dict):
        topic = {}
    base = normalize_negotiation_item(topic)
    resume_src = resume if isinstance(resume, dict) else topic.get("resume")
    summary = _resume_summary(resume_src) or {}
    if isinstance(resume_src, dict):
        summary = _enrich_resume_card(resume_src, summary)
    actions = []
    for raw in topic.get("actions") or []:
        normalized = _normalize_action(raw)
        if normalized:
            actions.append(normalized)
    hh_url = (
        topic.get("alternate_url")
        or topic.get("employer_url")
        or topic.get("url")
        or (summary.get("alternate_url") if summary else None)
    )
    return {
        **base,
        "resume": summary or None,
        "actions": actions,
        "hh_url": hh_url,
        "messages_url": topic.get("messages_url"),
    }


def _collection_meta(collections: list) -> list[dict]:
    return [
        {
            "id": c.get("id"),
            "name": c.get("name"),
            "url": c.get("url"),
            "counters": c.get("counters"),
        }
        for c in collections
        if isinstance(c, dict) and c.get("id")
    ]


async def list_employer_vacancies_normalized(
    hh: SimpleHHClient,
    *,
    archived: bool = False,
    page: int = 0,
    per_page: int = 50,
    all_accessible: bool = True,
    manager_id: str | None = None,
    manager_ids: str | None = None,
    text: str | None = None,
) -> dict:
    data = await hh.list_employer_vacancies(
        archived=archived,
        page=page,
        per_page=per_page,
        all_accessible=all_accessible,
        manager_id=manager_id,
        manager_ids=manager_ids,
        text=text,
    )
    if not isinstance(data, dict):
        data = {}
    items = [normalize_vacancy_item(i) for i in (data.get("items") or []) if isinstance(i, dict)]
    out = {
        "items": items,
        "found": data.get("found", len(items)),
        "pages": data.get("pages", 0),
        "page": data.get("page", page),
        "per_page": data.get("per_page", per_page),
        "archived": archived,
        "all_accessible": bool(all_accessible) and not manager_id and not manager_ids,
    }
    if data.get("_all_accessible_fallback"):
        out["warning"] = (
            "HH вернул только вакансии текущего менеджера токена "
            "(нет прав all_accessible). Переавторизуйте приложение под админом работодателя."
        )
        out["all_accessible"] = False
    return out


async def list_vacancy_negotiations_normalized(
    hh: SimpleHHClient,
    vacancy_id: str,
    *,
    collection: str = "response",
    page: int = 0,
    per_page: int = 50,
) -> dict:
    """
    Load negotiations for a HH vacancy from a named collection
    (response | consider | phone_interview | assessment | ...).
    """
    meta = await hh.get_negotiations_meta(str(vacancy_id))
    if not isinstance(meta, dict):
        meta = {}
    collections = meta.get("collections") or []
    coll_meta = _collection_meta(collections)

    coll = next((c for c in collections if isinstance(c, dict) and c.get("id") == collection), None)
    # Fallback: first non-empty / first available collection
    if not coll and collections:
        coll = next(
            (
                c for c in collections
                if isinstance(c, dict)
                and ((c.get("counters") or {}).get("total") or 0) > 0
            ),
            None,
        ) or next((c for c in collections if isinstance(c, dict) and c.get("id")), None)
        if coll:
            collection = coll.get("id") or collection

    if not coll:
        return {
            "items": [],
            "found": 0,
            "pages": 0,
            "page": page,
            "per_page": per_page,
            "collection": collection,
            "collections": coll_meta,
            "available_collections": [c["id"] for c in coll_meta],
            "warning": f"Collection '{collection}' not found",
        }

    url = (coll.get("url") or "").strip()
    if not url:
        raise HTTPException(502, f"HH collection '{collection}' has no url")

    try:
        page_data = await hh.list_negotiations_collection(url, page=page, per_page=per_page)
    except Exception as e:
        logger.error("Failed to load negotiations collection %s: %s", collection, e)
        raise

    if not isinstance(page_data, dict):
        page_data = {}
    raw_items = page_data.get("items") or []
    items = [normalize_negotiation_item(i) for i in raw_items if isinstance(i, dict)]

    return {
        "items": items,
        "found": page_data.get("found", len(items)),
        "pages": page_data.get("pages", 0),
        "page": page_data.get("page", page),
        "per_page": page_data.get("per_page", per_page),
        "collection": collection,
        "collections": coll_meta,
    }
