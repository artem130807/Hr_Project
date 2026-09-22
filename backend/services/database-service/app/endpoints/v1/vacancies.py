from typing import Any
import asyncio
import re

import httpx
from fastapi import APIRouter, Body, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.schemas.v1.vacancies import CreateVacancy, ReadVacancy, TestsForVacancy, VacancyUpdate, VacancyPostSchema, VacancyOption
from app.schemas.v1.tests import TestReadWOQuestions
from app.db.middleware import get_db
from app.db.v1.models import Vacancy, BotUser, Candidate, CandidateVacancyRelation, VacancyTestRelation, Test
from app.schemas.v1.vacancies import VacancyFilters, Area, Salary, IDRef, VacancyProperties
import app.config as conf
from app.app_logging import logger

router = APIRouter()


def _hh_service_base() -> str:
    base = (conf.HH_SERVICE_URL or "").rstrip("/")
    if not base:
        raise HTTPException(
            status_code=503,
            detail="HH service is not configured (HH_SERVICE_INTERNAL)",
        )
    return base


def _mint_service_bearer() -> str:
    """JWT signed by database-service private key — always verifiable via /v1/token/verify."""
    from app.utils.utils import create_token
    from app.config import ACCESS_TOKEN_EXPIRES, CLIENT_ID

    sub = CLIENT_ID or "database-service"
    token, _expires = create_token(
        data={"sub": sub, "type": "service"},
        expires_delta=ACCESS_TOKEN_EXPIRES,
    )
    return f"Bearer {token}"


def _parse_hh_response(resp: httpx.Response) -> tuple[Any, Any, int]:
    try:
        payload = resp.json() if resp.content else None
    except Exception:
        payload = None

    if isinstance(payload, dict) and "detail" in payload:
        detail = payload["detail"]
    elif payload is not None:
        detail = payload
    else:
        detail = resp.text or resp.reason_phrase or f"HH proxy HTTP {resp.status_code}"
    return payload, detail, resp.status_code


def _detail_as_text(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    return str(detail)


def _is_proxy_auth_failure(status_code: int, detail: Any) -> bool:
    """True only for DB↔HH auth failures — not HH.ru business 403s (duplicate, area, …)."""
    if status_code not in (401, 403):
        return False
    text = _detail_as_text(detail).lower()
    if (
        "hh api error" in text
        or "duplicate" in text
        or "chosen_area" in text
        or '"errors"' in text
        or ("vacancies" in text and "found" in text)
    ):
        return False
    if "invalid internal proxy token" in text:
        return True
    if "could not validate credentials" in text:
        return True
    if "token has expired" in text:
        return True
    return status_code == 401


async def _proxy_vacancy_to_hh(
    method: str,
    vacancy_id: int,
    json_body: Any = None,
    timeout: float = 90.0,
) -> Any:
    """Forward publish/update/delete to hh-service.

    Auth strategy (avoids JWKS drift with user tokens):
    1) Prefer /v1/internal/vacancy/{id} + X-Internal-Token (try every known secret)
    2) Fallback /v1/vacancy/{id} with freshly minted service JWT
    """
    base = _hh_service_base()
    secrets = list(getattr(conf, "INTERNAL_HH_PROXY_TOKENS", None) or [])
    if not secrets and conf.INTERNAL_HH_PROXY_TOKEN:
        secrets = [str(conf.INTERNAL_HH_PROXY_TOKEN)]

    attempts: list[str] = []
    detail: Any = "Could not validate credentials"
    detail_text = _detail_as_text(detail)
    status_code = 401
    probe = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            probe_resp = await client.get(f"{base}/v1/proxy-auth-info", timeout=min(5.0, timeout))
            if probe_resp.status_code == 200:
                probe = probe_resp.json() if probe_resp.content else {"ok": True}
                attempts.append(f"probe: {probe.get('proxy_auth', 'ok')}")
            else:
                attempts.append(f"probe: HTTP {probe_resp.status_code}")
        except httpx.RequestError as e:
            attempts.append(f"probe: unreachable ({e.__class__.__name__})")

        for idx, secret in enumerate(secrets):
            internal_url = f"{base}/v1/internal/vacancy/{vacancy_id}"
            try:
                resp = await client.request(
                    method,
                    internal_url,
                    headers={"X-Internal-Token": str(secret)},
                    json=json_body,
                )
            except httpx.RequestError as e:
                raise HTTPException(502, detail=f"HH service unreachable: {e}") from e

            payload, detail, status_code = _parse_hh_response(resp)
            detail_text = _detail_as_text(detail)
            attempts.append(f"internal[{idx}]: HTTP {status_code}")
            if resp.is_success:
                return payload
            if status_code == 404:
                break
            if _is_proxy_auth_failure(status_code, detail):
                continue
            if status_code == 409 and "Публикация невозможна" in detail_text:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "На сервере старая версия hh-service с блокировкой по портретам/слотам. "
                        "Нужно задеплоить актуальный hh-service. Исходная ошибка: "
                        f"{detail_text}"
                    ),
                )
            raise HTTPException(status_code=status_code, detail=detail)

        url = f"{base}/v1/vacancy/{vacancy_id}"
        headers: dict[str, str] = {"Authorization": _mint_service_bearer()}
        try:
            resp = await client.request(method, url, headers=headers, json=json_body)
        except httpx.RequestError as e:
            raise HTTPException(502, detail=f"HH service unreachable: {e}") from e

        payload, detail, status_code = _parse_hh_response(resp)
        detail_text = _detail_as_text(detail)
        attempts.append(f"jwt: HTTP {status_code}")
        if resp.is_success:
            return payload

    if status_code == 409 and "Публикация невозможна" in detail_text:
        raise HTTPException(
            status_code=502,
            detail=(
                "На сервере старая версия hh-service с блокировкой по портретам/слотам. "
                "Нужно задеплоить актуальный hh-service. Исходная ошибка: "
                f"{detail_text}"
            ),
        )

    if _is_proxy_auth_failure(status_code, detail) or any(
        a.startswith("probe: HTTP 404") for a in attempts
    ):
        probe_hint = ""
        if any(a.startswith("probe: HTTP 404") for a in attempts):
            probe_hint = (
                " hh-service НЕ содержит /v1/proxy-auth-info — образ устарел, "
                "обязательно пересоберите и задеплойте hh-service."
            )
        elif isinstance(probe, dict) and probe.get("internal_secret_configured") is False:
            probe_hint = (
                " На hh-service не задан INTERNAL_PROXY_SECRET/HH_SERVICE_CLIENT_SECRET/DB_CLIENT_SECRET."
            )
        raise HTTPException(
            status_code=502,
            detail=(
                "hh-service отклонил авторизацию прокси публикации. "
                "Нужен актуальный hh-service (dual-auth) и совпадающий секрет "
                "(INTERNAL_PROXY_SECRET или HH_SERVICE_CLIENT_SECRET) на обоих сервисах. "
                f"Секретов на database-service: {len(secrets)}. "
                f"Попытки: {'; '.join(attempts)}."
                f"{probe_hint} "
                f"Ответ hh-service: {detail_text}"
            ),
        )

    raise HTTPException(status_code=status_code, detail=detail)


@router.get('/vacancies', response_model=list[ReadVacancy], status_code=status.HTTP_200_OK)
async def get_all_vacancies_endpoint(filters: VacancyFilters = Query(),
                                     db: AsyncSession = Depends(get_db)):
    query = select(Vacancy)
    if filters.department:
        query = query.where(Vacancy.department == filters.department)
    if filters.employment_id:
        query = query.where(Vacancy.employment_id == filters.employment_id)
    if filters.salary_from is not None:
        query = query.where(Vacancy.salary_from >= filters.salary_from)
    if filters.salary_to is not None:
        query = query.where(Vacancy.salary_to <= filters.salary_to) 

    result = await db.execute(query)
    vacancies = result.scalars().all()
    return vacancies


@router.get('/vacancy/active/telegram/{telegram_id}', response_model=ReadVacancy, status_code=status.HTTP_200_OK)
async def get_vacancy_by_telegram_id(telegram_id: str,
                                     db: AsyncSession = Depends(get_db)):
    """
    Get active vacancy for candidate via related telegram_id
    """
    query = (select(Vacancy)
             .join(CandidateVacancyRelation)
             .join(Candidate)
             .join(BotUser)
             .where((BotUser.telegram_id==telegram_id) & (CandidateVacancyRelation.is_active == True))
             )
    result = await db.execute(query)
    vacancy = result.scalars().first()
    if not vacancy:
        raise HTTPException(404, 'Vacancy not found')
    return vacancy


@router.get('/vacancy/hh/{hh_id}', response_model=ReadVacancy)
async def get_vacancy_by_hh_id_endpoint(
    hh_id: str,
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Vacancy)
        .where(Vacancy.hh_vacancy_id == hh_id)
    )
    result = await db.execute(query)
    vacancy: Vacancy | None = result.scalar_one_or_none()
    if not vacancy:
        raise HTTPException(404, 'Vacancy not found')
    return vacancy


@router.get('/vacancy/{vacancy_id}', response_model=ReadVacancy, status_code=status.HTTP_200_OK)
async def get_vacancy_by_id_endpoint(vacancy_id: int,
                                     db: AsyncSession = Depends(get_db)):
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(404, 'Vacancy not found')
    return vacancy


@router.post('/vacancy/{vacancy_id}/make-template', response_model=ReadVacancy)
async def make_vacancy_template_endpoint(vacancy_id: int, db: AsyncSession = Depends(get_db)):
    """Clone vacancy as a reusable template (TZ: Сделать шаблон)."""
    src = await db.get(Vacancy, vacancy_id)
    if not src:
        raise HTTPException(404, "Vacancy not found")

    data = {
        c.name: getattr(src, c.name)
        for c in Vacancy.__table__.columns
        if c.name not in ("id", "created_at", "updated_at", "hh_vacancy_id", "hh_vacancy_url")
    }
    data["name"] = f"{src.name} (шаблон)"
    data["is_template"] = True
    data["hh_vacancy_id"] = None
    data["hh_vacancy_url"] = None
    clone = Vacancy(**data)
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return clone


@router.post('/vacancy', response_model=ReadVacancy, status_code=status.HTTP_201_CREATED)
async def post_vacancy_endpoint(data: CreateVacancy,
                                db: AsyncSession = Depends(get_db)):
    payload = data.model_dump()
    if payload.get("is_template") is None:
        payload["is_template"] = False
    vacancy = Vacancy(**payload)
    db.add(vacancy)
    await db.commit()
    await db.refresh(vacancy)
    return vacancy


async def _background_remove_hh_vacancy(hh_vacancy_id: str) -> None:
    """Fire-and-forget HH archive+hide so local DELETE never waits on HH/network."""
    try:
        await _remove_hh_vacancy_now(hh_vacancy_id)
    except Exception as e:
        logger.warning("background HH remove error hh_id=%s: %s", hh_vacancy_id, e)


def _hh_id_from_local_vacancy(vacancy: Vacancy) -> str | None:
    if vacancy.hh_vacancy_id:
        return str(vacancy.hh_vacancy_id)
    url = str(vacancy.hh_vacancy_url or "")
    m = re.search(r"/vacancy/(\d+)", url)
    return m.group(1) if m else None


async def _remove_hh_vacancy_now(hh_vacancy_id: str) -> None:
    """Archive+hide on HH by id (awaits completion). Raises on hard failure."""
    base = _hh_service_base()
    secrets = list(getattr(conf, "INTERNAL_HH_PROXY_TOKENS", None) or [])
    if not secrets and conf.INTERNAL_HH_PROXY_TOKEN:
        secrets = [str(conf.INTERNAL_HH_PROXY_TOKEN)]
    headers: dict[str, str] = {}
    if secrets:
        headers["X-Internal-Token"] = str(secrets[0])
    else:
        headers["Authorization"] = _mint_service_bearer()

    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.delete(
            f"{base}/v1/internal/hh-vacancy/{hh_vacancy_id}",
            headers=headers,
        )
        if resp.status_code >= 400:
            resp = await client.delete(
                f"{base}/v1/hh-vacancy/{hh_vacancy_id}",
                headers={"Authorization": _mint_service_bearer()},
            )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Не удалось снять вакансию с HH.ru (hh_id={hh_vacancy_id}): "
                    f"HTTP {resp.status_code} {(resp.text or '')[:300]}"
                ),
            )


@router.patch('/vacancy/{vacancy_id}', response_model=ReadVacancy)
async def update_vacancy_endpoint(
    vacancy_id: int,
    data: VacancyUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update local vacancy, then push to HH.ru when already published.

    Local commit always wins: HH failures become soft warnings
    (`hh_synced=false`, `hh_sync_error`) so edit UX is not blocked by HH outages.
    """
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vacancy, field, value)

    # Backfill hh_vacancy_id from URL so hh-service update path can resolve it
    resolved_hh = _hh_id_from_local_vacancy(vacancy)
    if resolved_hh and not vacancy.hh_vacancy_id:
        vacancy.hh_vacancy_id = str(resolved_hh)

    await db.commit()
    await db.refresh(vacancy)

    touch_fields = set(update_data.keys())
    link_only = bool(touch_fields) and touch_fields <= {"hh_vacancy_id", "hh_vacancy_url"}

    hh_synced: bool | None = None
    hh_sync_error: str | None = None

    # Keep HH.ru in sync when vacancy is already published there
    if not link_only and vacancy.hh_vacancy_id:
        if not conf.HH_SERVICE_URL:
            hh_synced = False
            hh_sync_error = "HH service is not configured (HH_SERVICE_INTERNAL)"
            logger.warning(
                "HH sync skipped for vacancy=%s: HH_SERVICE_INTERNAL unset",
                vacancy_id,
            )
        else:
            try:
                await _proxy_vacancy_to_hh("PUT", vacancy_id, timeout=45.0)
                hh_synced = True
                await db.refresh(vacancy)
            except HTTPException as e:
                hh_synced = False
                hh_sync_error = _detail_as_text(e.detail)
                logger.warning(
                    "HH sync soft-failed after local PATCH vacancy=%s: %s",
                    vacancy_id,
                    hh_sync_error,
                )

    result = ReadVacancy.model_validate(vacancy)
    if hh_synced is not None:
        result.hh_synced = hh_synced
        result.hh_sync_error = hh_sync_error
    return result


@router.delete('/vacancy/{vacancy_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_vacancy_endpoint(vacancy_id: int, db: AsyncSession = Depends(get_db)):
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    # Local lifecycle and HH publication lifecycle are intentionally independent.
    # Explicit DELETE /vacancy/{id}/hh remains the only operation that archives/hides on HH.

    # Clear FK dependents that are not cascaded on Vacancy (auto_search blocks DELETE)
    from app.db.v1.models import AutoSearch, ReviewedResume, VacancyTestRelation

    auto_rows = (
        await db.execute(select(AutoSearch).where(AutoSearch.vacancy_id == vacancy_id))
    ).scalars().all()
    for auto in auto_rows:
        reviewed = (
            await db.execute(
                select(ReviewedResume).where(ReviewedResume.auto_search_id == auto.id)
            )
        ).scalars().all()
        for row in reviewed:
            await db.delete(row)
        await db.delete(auto)

    test_rels = (
        await db.execute(
            select(VacancyTestRelation).where(VacancyTestRelation.vacancy_id == vacancy_id)
        )
    ).scalars().all()
    for rel in test_rels:
        await db.delete(rel)

    await db.delete(vacancy)
    await db.commit()

    return None


@router.get("/vacancy/{vacancy_id}/description", response_model=str, status_code=status.HTTP_200_OK)
async def get_vacancy_description(vacancy_id: int, db: AsyncSession = Depends(get_db)) -> str:
    """
    Creates text description of vacancy"""
    query = select(Vacancy).where(Vacancy.id == vacancy_id)
    result = await db.execute(query)
    vacancy: Vacancy | None = result.scalar_one_or_none()

    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    if not vacancy.description:
        raise HTTPException(404, 'Vacancy has not description yet')
    
    return vacancy.description


@router.post('/vacancy/{vacancy_id}/add_tests', response_model=list[TestReadWOQuestions], status_code=status.HTTP_201_CREATED)
async def post_vacancy_to_test_relation_endpoint(vacancy_id: int,
                                                 data: TestsForVacancy,
                                                 db: AsyncSession = Depends(get_db)):
    """
    Creates relations between vacanies and tests"""
    relations = []
    for test_id in data.test_ids:
        relation = VacancyTestRelation(vacancy_id=vacancy_id, 
                                       test_id=test_id)
        db.add(relation)
        relations.append(relation)
    await db.commit()
    test_ids = [rel.test_id for rel in relations]
    if test_ids:
        query = select(Test).where(Test.id.in_(test_ids))
        result = await db.execute(query)
        tests = result.scalars().all()
        return tests
    return []


@router.get('/vacancy/{vacancy_id}/tests', status_code=status.HTTP_200_OK)
async def get_tests_for_vacancy_endpoint(vacancy_id: int,
                                        db: AsyncSession = Depends(get_db)) -> list[int]:
    """
    Retrieves test ids for current vacancy by vacancy id.
    Empty list when none are linked (not 404 — UI treats that as normal).
    """
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(404, "Vacancy not found")
    query = select(VacancyTestRelation.test_id).where(VacancyTestRelation.vacancy_id == vacancy_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.put('/vacancy/{vacancy_id}/update_tests', status_code=status.HTTP_200_OK)
async def update_tests_for_vacancy_endpoint(vacancy_id: int,
                                            data: TestsForVacancy,
                                            db: AsyncSession = Depends(get_db)) -> list[int]:
    """
    Updates tests related to vacancy
    """
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    result = await db.execute(
        select(VacancyTestRelation).where(VacancyTestRelation.vacancy_id == vacancy_id)
    )
    existing_relations = {relation.test_id: relation for relation in result.scalars()}
    desired_test_ids = set(data.test_ids)

    # add new relations
    for test_id in desired_test_ids - existing_relations.keys():
        db.add(VacancyTestRelation(vacancy_id=vacancy_id, test_id=test_id))

    # remove outdated relations
    for test_id, relation in existing_relations.items():
        if test_id not in desired_test_ids:
            await db.delete(relation)

    await db.commit()

    result = await db.execute(
        select(VacancyTestRelation.test_id).where(VacancyTestRelation.vacancy_id == vacancy_id)
    )
    return result.scalars().all()


@router.get('/vacancy/{vacancy_id}/map-to-hh', response_model=VacancyPostSchema)
async def map_vacancy_to_hh_endpoint(
    vacancy_id: int,
    db: AsyncSession = Depends(get_db)
):
    # --- 1. Получаем вакансию из БД
    result = await db.execute(select(Vacancy).where(Vacancy.id == vacancy_id))
    vacancy = result.scalar_one_or_none()

    if not vacancy:
        raise HTTPException(status_code=404, detail="Вакансия не найдена")

    description = (vacancy.description or "").strip()
    if len(description) < 200:
        raise HTTPException(
            status_code=400,
            detail=(
                "Описание вакансии должно быть не короче 200 символов для публикации на HH.ru "
                f"(сейчас {len(description)}). Сохраните описание и попробуйте снова."
            ),
        )

    role_ids = [str(r) for r in (vacancy.professional_roles_id or []) if r]
    if not role_ids:
        raise HTTPException(
            status_code=400,
            detail="Укажите профессиональную роль перед публикацией на HH.ru",
        )

    if not vacancy.area_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Укажите город (местоположение) перед публикацией на HH.ru. "
                "Нужен именно город, а не только регион."
            ),
        )

    experience_id = vacancy.total_work_expirience
    if hasattr(experience_id, "value"):
        experience_id = experience_id.value
    experience_id = str(experience_id or "noExperience")

    type_id = str(vacancy.vacancy_type_id or "open")
    billing_id = str(vacancy.billing_type_id or "standard")
    # Guard: billing ids sometimes stored in vacancy_type_id
    _billing = {"free", "standard", "standard_plus", "premium"}
    _types = {"open", "closed", "anonymous", "direct"}
    if type_id in _billing:
        billing_id = type_id if billing_id not in _billing else billing_id
        type_id = "open"
    if type_id not in _types:
        type_id = "open"
    if billing_id not in _billing:
        billing_id = "standard"

    # --- 2. Формируем маппинг в структуру HH
    from app.db.v1.models import CompanyContact
    from app.utils.hh_contacts import contacts_from_company_contact

    contact_row = (
        await db.execute(select(CompanyContact).order_by(CompanyContact.id.asc()).limit(1))
    ).scalars().first()
    if not contact_row:
        raise HTTPException(
            status_code=400,
            detail=(
                "Нет контактного лица компании для HH.ru. "
                "Добавьте контакт в разделе «Контакты» перед публикацией."
            ),
        )
    contacts = contacts_from_company_contact(contact_row)

    hh_data = {
        "name": vacancy.name,
        "area": Area(id=str(vacancy.area_id)),
        "salary": Salary(
            from_=vacancy.salary_from,
            to=vacancy.salary_to,
            currency=vacancy.currency_id or "RUR",
            gross=vacancy.gross if vacancy.gross is not None else False,
        ) if vacancy.salary_from or vacancy.salary_to else None,
        "description": description,
        "employment": IDRef(id=str(vacancy.employment_id or "full")),
        "schedule": IDRef(id=str(vacancy.schedule_id or "fullDay")),
        "experience": IDRef(id=experience_id),
        "professional_roles": [IDRef(id=role_id) for role_id in role_ids],
        "vacancy_properties": VacancyProperties(),
        "type": IDRef(id=type_id),
        "billing_type": IDRef(id=billing_id),
        "contacts": contacts,
    }

    # --- 3. Возвращаем корректно типизированную модель
    return VacancyPostSchema(**hh_data)



@router.post("/vacancy/{vacancy_id}/hh")
async def publish_vacancy_to_hh_proxy(
    vacancy_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Publish vacancy to HH.ru via hh-service (avoids broken /hh ingress)."""
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(404, f"Вакансия #{vacancy_id} не найдена")
    return await _proxy_vacancy_to_hh("POST", vacancy_id, json_body={})


@router.put("/vacancy/{vacancy_id}/hh")
async def sync_vacancy_to_hh_proxy(
    vacancy_id: int,
    db: AsyncSession = Depends(get_db),
):
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(404, f"Вакансия #{vacancy_id} не найдена")
    return await _proxy_vacancy_to_hh("PUT", vacancy_id, json_body={})


@router.delete("/vacancy/{vacancy_id}/hh")
async def remove_vacancy_from_hh_proxy(
    vacancy_id: int,
    db: AsyncSession = Depends(get_db),
):
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(404, f"Вакансия #{vacancy_id} не найдена")
    return await _proxy_vacancy_to_hh("DELETE", vacancy_id)


@router.get('/vacancies/published', response_model=list[ReadVacancy])
async def get_published_vacancies(
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Vacancy).
        where(Vacancy.hh_vacancy_id != None)
    )
    result = await db.execute(query)
    vacancies = result.scalars().all()

    return vacancies


@router.get('/vacancies/options', response_model=list[VacancyOption])
async def get_vacancy_options(
    hh_only: bool = Query(
        False,
        description="If true, only vacancies published on hh.ru (hh_vacancy_id set)",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Slim id+name list for UI filters (avoids shipping full vacancy descriptions)."""
    query = select(Vacancy.id, Vacancy.name, Vacancy.hh_vacancy_id, Vacancy.hh_vacancy_url)
    if hh_only:
        query = query.where(Vacancy.hh_vacancy_id.is_not(None))
    query = query.order_by(Vacancy.name.asc(), Vacancy.id.asc())
    result = await db.execute(query)
    return [
        VacancyOption(
            id=row.id,
            name=row.name,
            hh_vacancy_id=row.hh_vacancy_id,
            hh_vacancy_url=row.hh_vacancy_url,
        )
        for row in result.all()
    ]


async def _proxy_hh_import(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: Any = None,
    timeout: float = 60.0,
) -> Any:
    """Proxy HH import/list endpoints (employer vacancies, negotiations)."""
    base = _hh_service_base()
    secrets = list(getattr(conf, "INTERNAL_HH_PROXY_TOKENS", None) or [])
    if not secrets and getattr(conf, "INTERNAL_HH_PROXY_TOKEN", None):
        secrets = [str(conf.INTERNAL_HH_PROXY_TOKEN)]

    # Normalize query values (bool → lowercase) for FastAPI Query parsing
    safe_params: dict[str, str] | None = None
    if params:
        safe_params = {}
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, bool):
                safe_params[key] = "true" if value else "false"
            else:
                safe_params[key] = str(value)

    url = f"{base}/v1/{path.lstrip('/')}"
    last_detail = None
    last_status = 502
    request_kwargs: dict[str, Any] = {"params": safe_params}
    if json_body is not None:
        request_kwargs["json"] = json_body

    async with httpx.AsyncClient(timeout=timeout) as client:
        for secret in secrets or [None]:
            headers: dict[str, str] = {}
            if secret:
                headers["X-Internal-Token"] = str(secret)
            else:
                headers["Authorization"] = _mint_service_bearer()
            try:
                resp = await client.request(method, url, headers=headers, **request_kwargs)
            except httpx.RequestError as e:
                last_detail = str(e)
                continue
            payload, detail, status_code = _parse_hh_response(resp)
            if status_code < 400:
                return payload
            last_detail, last_status = detail, status_code
            if not _is_proxy_auth_failure(status_code, detail):
                break

        headers = {"Authorization": _mint_service_bearer()}
        try:
            resp = await client.request(method, url, headers=headers, **request_kwargs)
            payload, detail, status_code = _parse_hh_response(resp)
            if status_code < 400:
                return payload
            last_detail, last_status = detail, status_code
        except httpx.RequestError as e:
            last_detail = str(e)

    # Never bubble 401/403 proxy-auth to the browser — FE treats 401 as session logout.
    status_out = last_status if isinstance(last_status, int) else 502
    if _is_proxy_auth_failure(status_out, last_detail):
        status_out = 502
        last_detail = f"HH service auth failed: {last_detail}"
    raise HTTPException(status_code=status_out, detail=last_detail)


@router.get("/hh/employer-vacancies")
async def proxy_employer_vacancies(
    archived: bool = Query(False),
    page: int = Query(0, ge=0),
    per_page: int = Query(50, ge=1, le=100),
    all_accessible: bool = Query(True),
    manager_id: str | None = Query(None),
    manager_ids: str | None = Query(None),
    text: str | None = Query(None),
):
    """Live list of company vacancies from HH.ru (via hh-service)."""
    params: dict = {
        "archived": archived,
        "page": page,
        "per_page": per_page,
        "all_accessible": all_accessible,
    }
    if manager_id:
        params["manager_id"] = manager_id
    if manager_ids:
        params["manager_ids"] = manager_ids
    if text:
        params["text"] = text
    return await _proxy_hh_import(
        "GET",
        "hh/employer-vacancies",
        params=params,
    )


@router.get("/hh/vacancies/{hh_vacancy_id}/negotiations")
async def proxy_vacancy_negotiations(
    hh_vacancy_id: str,
    collection: str = Query("response"),
    page: int = Query(0, ge=0),
    per_page: int = Query(50, ge=1, le=100),
):
    """Отклики HH по вакансии (via hh-service)."""
    return await _proxy_hh_import(
        "GET",
        f"hh/vacancies/{hh_vacancy_id}/negotiations",
        params={"collection": collection, "page": page, "per_page": per_page},
    )


@router.post("/hh/vacancies/{hh_vacancy_id}/import")
async def proxy_import_hh_vacancy(
    hh_vacancy_id: str,
    department: str = Query(..., description="Local department enum value"),
):
    """Create local vacancy from HH + link hh_vacancy_id (via hh-service)."""
    return await _proxy_hh_import(
        "POST",
        f"hh/vacancies/{hh_vacancy_id}/import",
        params={"department": department},
    )


@router.post("/hh/vacancies/{hh_vacancy_id}/link")
async def proxy_link_hh_vacancy(
    hh_vacancy_id: str,
    local_vacancy_id: int = Query(...),
):
    return await _proxy_hh_import(
        "POST",
        f"hh/vacancies/{hh_vacancy_id}/link",
        params={"local_vacancy_id": local_vacancy_id},
    )


@router.post("/hh/vacancies/{hh_vacancy_id}/negotiations/{negotiation_id}/import")
async def proxy_import_negotiation(
    hh_vacancy_id: str,
    negotiation_id: str,
    collection: str = Query("response"),
):
    return await _proxy_hh_import(
        "POST",
        f"hh/vacancies/{hh_vacancy_id}/negotiations/{negotiation_id}/import",
        params={"collection": collection},
    )


@router.get("/hh/negotiations/{negotiation_id}")
async def proxy_negotiation_detail(negotiation_id: str):
    """Подробности отклика HH + доступные действия (via hh-service)."""
    return await _proxy_hh_import("GET", f"hh/negotiations/{negotiation_id}")


@router.post("/hh/negotiations/{negotiation_id}/actions/{action_id}")
async def proxy_negotiation_action(
    negotiation_id: str,
    action_id: str,
    body: dict | None = Body(default=None),
):
    """Выполнить действие HH по отклику (отказ / интервью / принят и т.д.)."""
    return await _proxy_hh_import(
        "POST",
        f"hh/negotiations/{negotiation_id}/actions/{action_id}",
        json_body=body if body is not None else {},
    )


@router.get("/hh/connect/link")
async def proxy_hh_auth_link():
    """Return HH OAuth authorize URL (plaintext).

    Path avoids `/auth` and `/oauth` — prod edge returned 404 for those URIs
    even when OpenAPI listed the route (employer-vacancies on same router worked).
    Prefer local build from HH_CLIENT_ID + HH_REDIRECT_URI.
    """
    from fastapi.responses import PlainTextResponse
    from urllib.parse import urlencode

    client_id = getattr(conf, "HH_CLIENT_ID", None)
    redirect_uri = getattr(conf, "HH_REDIRECT_URI", None)
    if client_id and redirect_uri:
        qs = urlencode(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "state": "hr_platform_hh_oauth",
            }
        )
        return PlainTextResponse(f"https://hh.ru/oauth/authorize?{qs}")

    payload = await _proxy_hh_import("GET", "auth/link", timeout=20.0)
    if isinstance(payload, str):
        url = payload.strip().strip('"').strip("'")
    elif isinstance(payload, dict) and payload.get("url"):
        url = str(payload["url"])
    else:
        url = str(payload or "").strip()
    if not url.startswith("http"):
        raise HTTPException(
            502,
            f"Unexpected auth link payload: {payload!r}. "
            "Set HH_CLIENT_ID and HH_REDIRECT_URI on database-service, "
            "or ensure hh-service /v1/auth/link works.",
        )
    return PlainTextResponse(url)


@router.get("/hh/connect/status")
async def proxy_hh_auth_passed():
    """Whether HH OAuth tokens are present (via hh-service)."""
    return await _proxy_hh_import("GET", "auth-passed", timeout=15.0)


@router.get("/hh/autosearch/vacancies/available")
async def proxy_hh_autosearch_available():
    return await _proxy_hh_import("GET", "autosearch/vacancies/available")


@router.get("/hh/autosearch/active")
async def proxy_hh_autosearch_active():
    return await _proxy_hh_import("GET", "autosearch/active")


@router.post("/hh/autosearch/{vacancy_id}/activate")
async def proxy_hh_autosearch_activate(vacancy_id: int):
    return await _proxy_hh_import("POST", f"autosearch/{vacancy_id}/activate")


@router.post("/hh/autosearch/{vacancy_id}/deactivate")
async def proxy_hh_autosearch_deactivate(vacancy_id: int):
    return await _proxy_hh_import("POST", f"autosearch/{vacancy_id}/deactivate")


@router.patch("/hh/autosearch/{vacancy_id}/invite-limit")
async def proxy_hh_autosearch_invite_limit(
    vacancy_id: int,
    invite_limit: int = Query(..., ge=1),
):
    return await _proxy_hh_import(
        "PATCH",
        f"autosearch/{vacancy_id}/invite-limit",
        params={"invite_limit": invite_limit},
    )


@router.get("/hh/subscription")
async def proxy_hh_subscription():
    return await _proxy_hh_import("GET", "hh/subscription")


@router.post("/hh/negotiations/subscribe")
async def proxy_hh_negotiations_subscribe(subscribe: bool = Query(...)):
    return await _proxy_hh_import(
        "POST",
        "negotiations/subscribe",
        params={"subscribe": subscribe},
    )

