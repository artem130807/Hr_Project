"""Product APIs: list employer HH vacancies and negotiations (отклики) per vacancy."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.clients.db_client import APICLient
from app.clients.hh.simple_hh_client import SimpleHHClient
from app.dependencies import get_db_client, get_hh_client
from app.utils.hh_import import (
    build_local_vacancy_from_hh,
    list_employer_vacancies_normalized,
    list_vacancy_negotiations_normalized,
    normalize_negotiation_detail,
)
from app.utils.resume_parsing import parse_hh_resume_to_candidate
from app.enums.v1.enums import CandidateStatus
from app.utils.candidate_lookup import find_existing_candidate_id, lookup_existing_candidates
from app.app_logging import logger

router = APIRouter()


class NegotiationActionBody(BaseModel):
    """Arguments for HH negotiation action (e.g. message for discard/interview)."""

    arguments: Optional[dict[str, Any]] = Field(default=None)


def _candidate_payload_from_resume(resume: dict, resume_id: str) -> dict:
    candidate_data = parse_hh_resume_to_candidate(resume)
    payload = candidate_data.model_dump(mode="json")
    link = (payload.get("hh_resume_link") or "").strip()
    if not link:
        payload["hh_resume_link"] = (
            resume.get("alternate_url")
            or f"https://hh.ru/resume/{resume_id}"
        )
    phone = payload.get("phone_number")
    if phone is not None and len(str(phone)) < 10:
        payload["phone_number"] = None
    return payload


async def _mark_already_candidates(items: list, db: APICLient) -> None:
    resume_ids = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rid = (item.get("resume") or {}).get("id") if isinstance(item.get("resume"), dict) else None
        if rid:
            resume_ids.append(str(rid))
        item["already_candidate"] = bool(item.get("already_candidate"))
        item["candidate_id"] = item.get("candidate_id")
    if not resume_ids:
        return
    found = await lookup_existing_candidates(db, resume_ids=resume_ids)
    by_resume = {}
    for row in found:
        if not isinstance(row, dict):
            continue
        rid = row.get("resume_id")
        cid = row.get("candidate_id")
        if rid and cid:
            by_resume[str(rid).lower()] = cid
    for item in items:
        if not isinstance(item, dict):
            continue
        rid = (item.get("resume") or {}).get("id") if isinstance(item.get("resume"), dict) else None
        cid = by_resume.get(str(rid).lower()) if rid else None
        if cid:
            item["already_candidate"] = True
            item["candidate_id"] = cid


@router.get("/hh/employer-vacancies")
async def get_employer_vacancies(
    archived: bool = Query(False, description="If true — archived vacancies"),
    page: int = Query(0, ge=0),
    per_page: int = Query(50, ge=1, le=100),
    all_accessible: bool = Query(
        True,
        description=(
            "HH: include vacancies of all managers accessible to the token "
            "(default true). Without this HH returns only the current manager."
        ),
    ),
    manager_id: Optional[str] = Query(None, description="Filter by one HH manager id"),
    manager_ids: Optional[str] = Query(None, description="Comma-separated HH manager ids"),
    text: Optional[str] = Query(None, description="Search by vacancy name"),
    hh: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client),
):
    """Вакансии компании уже опубликованные на HH.ru."""
    data = await list_employer_vacancies_normalized(
        hh,
        archived=archived,
        page=page,
        per_page=per_page,
        all_accessible=all_accessible,
        manager_id=manager_id,
        manager_ids=manager_ids,
        text=text,
    )
    # Enrich with local platform link if present
    for item in data.get("items") or []:
        hh_id = item.get("hh_vacancy_id")
        if not hh_id:
            continue
        try:
            local = await db.get(f"/vacancy/hh/{hh_id}")
            if local and isinstance(local, dict):
                item["local_vacancy_id"] = local.get("id")
                item["local_name"] = local.get("name")
            else:
                item["local_vacancy_id"] = None
        except Exception:
            item["local_vacancy_id"] = None
    return data


@router.get("/hh/vacancies/{hh_vacancy_id}/negotiations")
async def get_vacancy_negotiations(
    hh_vacancy_id: str,
    collection: str = Query(
        "response",
        description="HH collection id: response, consider, phone_interview, ...",
    ),
    page: int = Query(0, ge=0),
    per_page: int = Query(50, ge=1, le=100),
    hh: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client),
):
    """Отклики / переговоры по конкретной вакансии HH."""
    data = await list_vacancy_negotiations_normalized(
        hh,
        hh_vacancy_id,
        collection=collection,
        page=page,
        per_page=per_page,
    )
    await _mark_already_candidates(data.get("items") or [], db)
    return data


async def _load_negotiation_detail(
    hh: SimpleHHClient, negotiation_id: str, db: APICLient | None = None
) -> dict:
    topic = await hh.get_negotiation(str(negotiation_id))
    if not isinstance(topic, dict) or not topic.get("id"):
        raise HTTPException(404, "Negotiation not found")
    resume = None
    resume_obj = topic.get("resume") if isinstance(topic.get("resume"), dict) else None
    resume_id = (resume_obj or {}).get("id")
    if resume_id:
        try:
            resume = await hh.get_resume(str(resume_id))
        except Exception as e:
            logger.warning("GET resume %s for negotiation %s failed: %s", resume_id, negotiation_id, e)
    detail = normalize_negotiation_detail(topic, resume=resume if isinstance(resume, dict) else None)
    if db is not None:
        await _mark_already_candidates([detail], db)
    return detail


@router.get("/hh/negotiations/{negotiation_id}")
async def get_negotiation_detail(
    negotiation_id: str,
    hh: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client),
):
    """Подробности отклика + доступные действия HH (без сырых URL actions)."""
    return await _load_negotiation_detail(hh, negotiation_id, db=db)


@router.post("/hh/negotiations/{negotiation_id}/actions/{action_id}")
async def execute_negotiation_action_endpoint(
    negotiation_id: str,
    action_id: str,
    body: NegotiationActionBody = Body(default_factory=NegotiationActionBody),
    hh: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client),
):
    """
    Выполнить действие HH (отказ, приглашение, принят и т.д.).
    Синхронизация с hh.ru: метод/URL берутся из actions отклика на HH.
    """
    result = await hh.execute_negotiation_action(
        str(negotiation_id),
        str(action_id),
        arguments=body.arguments if body else None,
    )
    detail = await _load_negotiation_detail(hh, negotiation_id, db=db)
    return {
        "status": "ok",
        "action_id": str(action_id),
        "negotiation_id": str(negotiation_id),
        "result": result,
        "negotiation": detail,
    }


class CandidateHhActionBody(BaseModel):
    message: Optional[str] = None


def _add_hh_vacancy_id(ids: list[str], seen: set[str], raw) -> None:
    value = str(raw or "").strip()
    if not value or value in seen:
        return
    seen.add(value)
    ids.append(value)


def _hh_ids_from_vacancy_payload(payload) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    if isinstance(payload, dict):
        _add_hh_vacancy_id(ids, seen, payload.get("hh_vacancy_id"))
        nested = payload.get("vacancy")
        if isinstance(nested, dict):
            _add_hh_vacancy_id(ids, seen, nested.get("hh_vacancy_id"))
    return ids


def _relation_items(payload) -> list[dict]:
    items = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        items = payload.get("items") or []
    return [rel for rel in items if isinstance(rel, dict)]


def _hh_ids_from_relations(payload) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for rel in _relation_items(payload):
        _add_hh_vacancy_id(ids, seen, rel.get("hh_vacancy_id"))
        vac = rel.get("vacancy")
        if isinstance(vac, dict):
            _add_hh_vacancy_id(ids, seen, vac.get("hh_vacancy_id"))
    return ids


@router.post("/hh/candidates/{candidate_id}/actions/{action_id}")
async def sync_candidate_hh_action(
    candidate_id: int,
    action_id: str,
    body: CandidateHhActionBody = Body(default_factory=CandidateHhActionBody),
    hh: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client),
):
    """
    Найти отклик кандидата на HH и выполнить действие
    (consider / offer / interview / message).
    Используется, когда рекрутер меняет статус или отправляет тест/оффер/приглашение.
    """
    from app.utils.hh_candidate_sync import find_negotiation_id_for_resume, normalize_hh_resume_id

    wanted = str(action_id or "").strip().lower()
    if wanted not in {"consider", "offer", "interview", "message"}:
        raise HTTPException(
            400,
            "Поддерживаются только действия consider, offer, interview и message",
        )

    candidate = await db.get(f"/candidate/{candidate_id}")
    if not isinstance(candidate, dict):
        raise HTTPException(404, "Candidate not found")

    active = await db.get(f"/candidate/{candidate_id}/active-vacancy")
    hh_vacancy_ids = _hh_ids_from_vacancy_payload(active)

    resume_id = normalize_hh_resume_id(candidate.get("hh_resume_link"))
    if not resume_id:
        return {"status": "skipped", "reason": "no_hh_resume", "candidate_id": candidate_id}

    negotiation_id = None
    matched_vacancy_id = None
    tried: set[str] = set()

    async def _search(vac_ids: list[str]) -> None:
        nonlocal negotiation_id, matched_vacancy_id
        for hh_vacancy_id in vac_ids:
            if hh_vacancy_id in tried:
                continue
            tried.add(hh_vacancy_id)
            negotiation_id = await find_negotiation_id_for_resume(hh, str(hh_vacancy_id), resume_id)
            if negotiation_id:
                matched_vacancy_id = str(hh_vacancy_id)
                return

    await _search(hh_vacancy_ids)
    relations_payload = None
    if not negotiation_id:
        relations_payload = await db.get(f"/candidate/{candidate_id}/vacancies")
        await _search(_hh_ids_from_relations(relations_payload))

    if not negotiation_id:
        if not tried:
            has_relation = bool(_relation_items(relations_payload)) or isinstance(active, dict)
            reason = "vacancy_not_on_hh" if has_relation else "no_active_vacancy"
            return {"status": "skipped", "reason": reason, "candidate_id": candidate_id}
        logger.info(
            "HH negotiation not found for candidate %s vacancies %s resume %s",
            candidate_id,
            list(tried),
            resume_id,
        )
        return {
            "status": "skipped",
            "reason": "negotiation_not_found",
            "candidate_id": candidate_id,
            "hh_vacancy_id": next(iter(tried), None),
            "hh_vacancy_ids": list(tried),
        }

    message = (body.message or "").strip() or None
    if wanted == "consider":
        result = await hh.consider_negotiation(negotiation_id)
    elif wanted == "offer":
        result = await hh.offer_negotiation(negotiation_id, message=message)
    elif wanted == "interview":
        if not message:
            raise HTTPException(400, "message is required for action interview")
        result = await hh.interview_negotiation(negotiation_id, message=message)
    else:
        if not message:
            raise HTTPException(400, "message is required for action message")
        result = await hh.send_message_to_negotiation(negotiation_id, message)

    return {
        "status": "ok",
        "action_id": wanted,
        "candidate_id": candidate_id,
        "negotiation_id": negotiation_id,
        "hh_vacancy_id": matched_vacancy_id,
        "result": result,
    }


@router.post("/hh/vacancies/{hh_vacancy_id}/negotiations/{negotiation_id}/import")
async def import_negotiation_as_candidate(
    hh_vacancy_id: str,
    negotiation_id: str,
    collection: str = Query("response"),
    hh: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client),
):
    """
    Импорт одного отклика в платформу: создать кандидата + связь с локальной вакансией.
    Требует, чтобы HH-вакансия была привязана локально (hh_vacancy_id).
    """
    local_vacancy = await db.get(f"/vacancy/hh/{hh_vacancy_id}")
    if not local_vacancy or not isinstance(local_vacancy, dict):
        raise HTTPException(
            400,
            "Локальная вакансия с этим hh_vacancy_id не найдена. Сначала привяжите вакансию.",
        )

    resume_id = None
    # Prefer direct topic fetch (avoids scanning collection pages)
    try:
        topic = await hh._request("GET", f"/negotiations/{negotiation_id}")
        if isinstance(topic, dict):
            resume = topic.get("resume") if isinstance(topic.get("resume"), dict) else None
            resume_id = (resume or {}).get("id")
    except Exception as e:
        logger.warning("GET /negotiations/%s failed, fallback to collection scan: %s", negotiation_id, e)
        topic = None

    if not resume_id:
        found = None
        for page in range(0, 5):
            data = await list_vacancy_negotiations_normalized(
                hh, hh_vacancy_id, collection=collection, page=page, per_page=50
            )
            for item in data.get("items") or []:
                if str(item.get("id")) == str(negotiation_id):
                    found = item
                    break
            if found or not data.get("items"):
                break
            if page + 1 >= (data.get("pages") or 1):
                break
        if not found:
            raise HTTPException(404, "Negotiation not found in collection")
        resume_id = (found.get("resume") or {}).get("id")

    if not resume_id:
        raise HTTPException(400, "Resume id missing on negotiation")

    resume = await hh._request("GET", f"/resumes/{resume_id}")
    if not isinstance(resume, dict):
        raise HTTPException(502, "Empty resume from HH")

    payload = _candidate_payload_from_resume(resume, str(resume_id))
    existing_id = await find_existing_candidate_id(
        db,
        resume_id=str(resume_id),
        phone=payload.get("phone_number"),
        email=payload.get("email"),
    )
    if existing_id:
        logger.info(
            "Skip import HH negotiation %s — candidate %s already exists",
            negotiation_id,
            existing_id,
        )
        return {
            "status": "already_exists",
            "created": False,
            "candidate_id": existing_id,
            "local_vacancy_id": local_vacancy["id"],
            "negotiation_id": negotiation_id,
        }

    candidate_resp = await db.post(
        "/candidate",
        json=payload,
        raise_on_error=True,
    )
    if not candidate_resp or not candidate_resp.get("id"):
        raise HTTPException(502, "Failed to create candidate")

    await db.post(
        "/candidate/vacancy",
        json={
            "candidate_id": candidate_resp["id"],
            "vacancy_id": local_vacancy["id"],
            "status": CandidateStatus.applied.value,
            "is_active": True,
        },
        raise_on_error=True,
    )
    logger.info(
        "Imported HH negotiation %s → candidate %s / vacancy %s",
        negotiation_id,
        candidate_resp["id"],
        local_vacancy["id"],
    )
    return {
        "status": "ok",
        "created": True,
        "candidate_id": candidate_resp["id"],
        "local_vacancy_id": local_vacancy["id"],
        "negotiation_id": negotiation_id,
    }


@router.post("/hh/vacancies/{hh_vacancy_id}/import")
async def import_hh_vacancy_to_local(
    hh_vacancy_id: str,
    department: str = Query(
        ...,
        description="Local platform department (Departments enum value)",
    ),
    hh: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client),
):
    """Создать локальную вакансию из HH и сразу проставить hh_vacancy_id.

    Если локальная карточка с этим hh_vacancy_id уже есть — вернуть её без дубля.
    """
    existing = await db.get(f"/vacancy/hh/{hh_vacancy_id}")
    if isinstance(existing, dict) and existing.get("id") is not None:
        return {
            "status": "already_linked",
            "created": False,
            "local_vacancy_id": existing["id"],
            "hh_vacancy_id": str(hh_vacancy_id),
            "hh_vacancy_url": existing.get("hh_vacancy_url"),
            "vacancy": existing,
        }

    try:
        hh_vac = await hh.get_vacancy(str(hh_vacancy_id))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("HH get_vacancy(%s) failed during import: %s", hh_vacancy_id, e)
        raise HTTPException(502, f"Не удалось загрузить вакансию с HH: {e}") from e

    if not isinstance(hh_vac, dict) or not hh_vac.get("id"):
        raise HTTPException(502, "HH вернул пустую вакансию")

    payload = build_local_vacancy_from_hh(hh_vac, department)
    created = await db.post("/vacancy", json=payload, raise_on_error=True)
    if not created or not isinstance(created, dict):
        raise HTTPException(502, "Не удалось создать локальную вакансию")

    return {
        "status": "ok",
        "created": True,
        "local_vacancy_id": created.get("id"),
        "hh_vacancy_id": str(hh_vacancy_id),
        "hh_vacancy_url": created.get("hh_vacancy_url") or payload.get("hh_vacancy_url"),
        "vacancy": created,
    }


@router.post("/hh/vacancies/{hh_vacancy_id}/link")
async def link_hh_vacancy_to_local(
    hh_vacancy_id: str,
    local_vacancy_id: int = Query(..., description="Local vacancy id"),
    hh: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client),
):
    """Привязать уже опубликованную на HH вакансию к локальной записи.

    Works for active and archived HH vacancies. If HH GET fails (e.g. archived
    edge cases), still link using a constructed alternate_url.
    """
    url = f"https://hh.ru/vacancy/{hh_vacancy_id}"
    try:
        hh_vac = await hh.get_vacancy(str(hh_vacancy_id))
        if isinstance(hh_vac, dict) and hh_vac.get("alternate_url"):
            url = hh_vac["alternate_url"]
    except HTTPException as e:
        logger.warning(
            "HH get_vacancy(%s) failed during link (will use fallback url): %s",
            hh_vacancy_id,
            e.detail,
        )
    except Exception as e:
        logger.warning(
            "HH get_vacancy(%s) failed during link (will use fallback url): %s",
            hh_vacancy_id,
            e,
        )

    updated = await db.patch(
        f"/vacancy/{local_vacancy_id}",
        json={"hh_vacancy_id": str(hh_vacancy_id), "hh_vacancy_url": url},
        raise_on_error=True,
    )
    if not updated:
        raise HTTPException(502, "Failed to update local vacancy")
    return {
        "status": "ok",
        "local_vacancy_id": local_vacancy_id,
        "hh_vacancy_id": str(hh_vacancy_id),
        "hh_vacancy_url": url,
        "vacancy": updated,
    }


@router.post("/hh/local-vacancies/{vacancy_id}/run-filter")
async def run_local_vacancy_filter_now(
    vacancy_id: int,
    hh: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client),
):
    """Прогнать VacancyFilter порцией (лимит отказов), чтобы не нагружать HH API."""
    from app.tasks.auto_reject_filtered import auto_reject_filtered

    summary = await auto_reject_filtered(
        db, hh, vacancy_id=vacancy_id, include_viewed=True
    )
    return {"status": "ok", "summary": summary}
