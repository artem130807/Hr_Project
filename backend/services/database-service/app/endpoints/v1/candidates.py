from datetime import datetime, timezone
from math import ceil
from typing import Optional
import re

from fastapi import APIRouter, status, HTTPException, Depends, Query
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists, and_, func, or_, cast, String, desc, update
from sqlalchemy.exc import DataError, IntegrityError, ProgrammingError

from sqlalchemy.orm import aliased

from app.db.middleware import get_db
from app.db.v1.enums import (
    CandidateStatus, CandidateStage
)
from app.db.v1.models import (
    Candidate, CandidateVacancyRelation, Vacancy,
    CandidateTestResult, BotUser, CandidateQuestionAnswer,
    CandidateDocumentInvite, CandidateDocumentUploadSession,
    )
from app.schemas.v1.paginated_response import PaginatedResponse
from app.schemas.v1.candidates import (
    CandidateRead, CandidateCreate, CandidateUpdate,
    ReadCandidateVacancyRelation, CreateCandidateVacancyRelation,
    CandidateVacancyRelationUpdate, CandidateStatusSchema,
    CandidateFillInfoSchema, CandidateHTMLResponse, ChangeVacancyData,
    CandidateHhLookupResponse, CandidateHhLookupItem,
)
from app.utils.hh_resume import normalize_hh_resume_id, candidate_link_matches_resume_id
from app.schemas.v1.bot_users import BotUserRead
from app.schemas.v1.tests import CandidatTestResultRead
from app.schemas.v1.vacancies import ReadVacancy
from app.utils.ai import generate_candidate_summary, generate_vacancy_description, get_company_candidate_image, get_department_candidate_image
from app.utils.candidate_info import render_candidate_html_for_telegram
from app.utils.actor import actor_from_headers
from app.utils.audit import write_audit
from app.utils.hh_sync import sync_candidate_hh_action
from app.clients.api_client import APICLient
from app.dependencies import get_ai_client, get_hh_client

from app.app_logging import logger

router = APIRouter()

_TG_NAME_RE = re.compile(r"^[A-Za-z0-9_]{4,32}$")


def _telegram_from_bot_name(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).strip().lstrip("@")
    if not s or " " in s or not _TG_NAME_RE.match(s):
        return None
    return f"@{s}"


def _apply_telegram_fallback(candidate: Candidate, bot_username: Optional[str] = None) -> None:
    if getattr(candidate, "telegram_username", None):
        return
    fallback = _telegram_from_bot_name(bot_username)
    if fallback:
        candidate.telegram_username = fallback


def _attach_last_vacancy(candidate: Candidate) -> None:
    """Fill last_vacancy_* from loaded CandidateVacancyRelation rows (not ORM columns)."""
    relations = list(getattr(candidate, "vacancies", None) or [])
    if not relations:
        candidate.last_vacancy_id = getattr(candidate, "last_vacancy_id", None)
        candidate.last_vacancy_title = getattr(candidate, "last_vacancy_title", None)
        return

    def _updated(rel: CandidateVacancyRelation):
        return (
            getattr(rel, "status_updated_at", None)
            or getattr(rel, "updated_at", None)
            or getattr(rel, "created_at", None)
            or rel.id
        )

    active = [r for r in relations if getattr(r, "is_active", False)]
    chosen = max(active or relations, key=_updated)
    vacancy = getattr(chosen, "vacancy", None)
    candidate.last_vacancy_id = getattr(vacancy, "id", None) or getattr(chosen, "vacancy_id", None)
    candidate.last_vacancy_title = getattr(vacancy, "name", None)


@router.get("/candidates/by-hh-resume", response_model=CandidateHhLookupResponse)
async def lookup_candidates_by_hh_resume(
    resume_id: list[str] | None = Query(
        None,
        description="HH resume id or https://hh.ru/resume/<id>. Repeat for batch lookup.",
    ),
    phone: str | None = Query(None),
    email: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Find existing candidates by HH resume / phone / email — no duplicates on import."""
    resume_ids = [normalize_hh_resume_id(x) for x in (resume_id or [])]
    resume_ids = [x for x in resume_ids if x]
    phone_norm = (phone or "").strip() or None
    email_norm = (email or "").strip().lower() or None
    if not resume_ids and not phone_norm and not email_norm:
        raise HTTPException(400, "Передайте resume_id, phone или email")

    conditions = []
    for rid in resume_ids:
        conditions.append(Candidate.hh_resume_link.ilike(f"%{rid}%"))
    if phone_norm:
        conditions.append(Candidate.phone_number == phone_norm)
    if email_norm:
        conditions.append(func.lower(Candidate.email) == email_norm)

    result = await db.execute(
        select(Candidate).where(Candidate.archived_at.is_(None), or_(*conditions))
    )
    rows = result.scalars().all()

    items: list[CandidateHhLookupItem] = []
    seen: set[tuple] = set()

    def add_item(rid: Optional[str], candidate_id: int, matched_by: str) -> None:
        key = (rid, candidate_id, matched_by)
        if key in seen:
            return
        seen.add(key)
        items.append(
            CandidateHhLookupItem(
                resume_id=rid,
                candidate_id=candidate_id,
                matched_by=matched_by,
            )
        )

    for rid in resume_ids:
        for cand in rows:
            if candidate_link_matches_resume_id(cand.hh_resume_link, rid):
                add_item(rid, cand.id, "resume")
                break

    if phone_norm:
        for cand in rows:
            if (cand.phone_number or "").strip() == phone_norm:
                add_item(normalize_hh_resume_id(cand.hh_resume_link), cand.id, "phone")
                break

    if email_norm:
        for cand in rows:
            stored = (getattr(cand, "email", None) or "").strip().lower()
            if stored and stored == email_norm:
                add_item(normalize_hh_resume_id(cand.hh_resume_link), cand.id, "email")
                break

    return CandidateHhLookupResponse(items=items)


@router.get('/candidates', response_model=PaginatedResponse[CandidateRead])
async def get_all_candidates(
    status: CandidateStatus | None = Query(None),
    search: str | None = Query(None),
    vacancy_id: list[int] | None = Query(
        None,
        description="Local vacancy id(s). Repeat param for multi-select filter.",
    ),
    role_id: str | None = Query(None, description="HH professional role id"),
    is_perfect_candidate: bool | None = Query(None),
    category: str | None = Query(
        None,
        description="TZ category: candidate|archive|blacklist|staff",
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # Алиас для независимых подзапросов фильтрации
    cvr_alias = aliased(CandidateVacancyRelation)

    # === ЛОГИКА ВЫБОРА СВЯЗИ ДЛЯ ПОДЗАПРОСОВ ===
    # Если кандидат архивирован/в ЧС → берём ЛЮБУЮ последнюю связь
    # Если активен → только активную связь
    last_vacancy_filter = or_(
        Candidate.stage.in_([CandidateStage.archieved, CandidateStage.blacklisted]),
        CandidateVacancyRelation.is_active.is_(True)
    )

    # === 1. ПОДЗАПРОС ДЛЯ СОРТИРОВКИ (по дате обновления статуса) ===
    # Пробуем status_updated_at, если колонки нет — fallback на updated_at
    try:
        date_column = CandidateVacancyRelation.status_updated_at
    except AttributeError:
        date_column = CandidateVacancyRelation.updated_at

    latest_activity_subq = (
        select(func.max(date_column))
        .where(
            CandidateVacancyRelation.candidate_id == Candidate.id,
            CandidateVacancyRelation.is_active.is_(True)
        )
        .correlate(Candidate)
        .scalar_subquery()
    )

    # === 2. ПОДЗАПРОС ДЛЯ ФЛАГА perfect_candidate ===
    perfect_subq = (
        select(1)
        .where(
            cvr_alias.candidate_id == Candidate.id,
            cvr_alias.is_active.is_(True),
            cvr_alias.perfect_candidate.is_(True)
        )
        .correlate(Candidate)
    )

    # === 3. ПОДЗАПРОС ДЛЯ ТЕКУЩЕГО СТАТУСА ===
    current_status_subq = (
        select(CandidateVacancyRelation.status)
        .where(
            CandidateVacancyRelation.candidate_id == Candidate.id,
            CandidateVacancyRelation.is_active.is_(True)
        )
        .order_by(date_column.desc())
        .limit(1)
        .correlate(Candidate)
    )

    # === 4. ПОДЗАПРОСЫ ДЛЯ ПОСЛЕДНЕЙ ВАКАНСИИ (ID и TITLE) ===
    last_vacancy_id_subq = (
        select(CandidateVacancyRelation.vacancy_id)
        .where(
            CandidateVacancyRelation.candidate_id == Candidate.id,
            last_vacancy_filter
        )
        .order_by(CandidateVacancyRelation.updated_at.desc())
        .limit(1)
        .correlate(Candidate)
        .scalar_subquery()
    )

    last_vacancy_title_subq = (
        select(Vacancy.name)
        .join(
            CandidateVacancyRelation,
            CandidateVacancyRelation.vacancy_id == Vacancy.id
        )
        .where(
            CandidateVacancyRelation.candidate_id == Candidate.id,
            last_vacancy_filter
        )
        .order_by(CandidateVacancyRelation.updated_at.desc())
        .limit(1)
        .correlate(Candidate)
        .scalar_subquery()
    )

    bot_username_subq = (
        select(BotUser.name)
        .where(BotUser.id == Candidate.user_id)
        .correlate(Candidate)
        .scalar_subquery()
    )

    # === ОСНОВНОЙ ЗАПРОС ===
    query = select(
        Candidate,
        exists(perfect_subq).label("is_perfect_candidate"),
        current_status_subq.scalar_subquery().label("current_status"),
        last_vacancy_id_subq.label("last_vacancy_id"),
        last_vacancy_title_subq.label("last_vacancy_title"),
        bot_username_subq.label("bot_username"),
    ).where(Candidate.archived_at.is_(None))

    # === ФИЛЬТРАЦИЯ ===
    # Stages: PG enum labels = Python member *names* (employment, …).
    # Statuses: PG enum labels = Python member *values* (откликнулся, …).
    if category:
        cat = category.strip().lower()
        if cat == "archive":
            query = query.where(Candidate.stage == CandidateStage.archieved)
        elif cat == "blacklist":
            query = query.where(Candidate.stage == CandidateStage.blacklisted)
        elif cat == "staff":
            query = query.where(Candidate.stage == CandidateStage.hired)
        elif cat == "candidate":
            query = query.where(Candidate.stage == CandidateStage.employment)
        # legacy category ids (reserve/probation) removed with old statuses

    if status:
        from app.db.v1.enums import ARCHIVE_STATUSES

        status_value = status.value if hasattr(status, "value") else status
        if status in ARCHIVE_STATUSES:
            # Archive-like statuses may live on inactive relations + stage
            status_subq = (
                select(1)
                .where(
                    CandidateVacancyRelation.candidate_id == Candidate.id,
                    CandidateVacancyRelation.status == status_value,
                )
                .correlate(Candidate)
            )
            query = query.where(
                or_(
                    Candidate.stage == CandidateStage.archieved,
                    Candidate.stage == CandidateStage.blacklisted,
                    exists(status_subq),
                )
            )
        else:
            status_subq = (
                select(1)
                .where(
                    CandidateVacancyRelation.candidate_id == Candidate.id,
                    CandidateVacancyRelation.status == status_value,
                    CandidateVacancyRelation.is_active.is_(True),
                )
                .correlate(Candidate)
            )
            query = query.where(exists(status_subq))

    if search:
        needle = search.strip()
        if needle:
            pattern = f"%{needle}%"
            # hard_skills is JSON list in DB — cast to text for substring match
            skills_text = cast(Candidate.hard_skills, String)
            query = query.where(
                or_(
                    Candidate.full_name.ilike(pattern),
                    Candidate.phone_number.ilike(pattern),
                    Candidate.telegram_username.ilike(pattern),
                    Candidate.email.ilike(pattern),
                    skills_text.ilike(pattern),
                )
            )

    vacancy_ids = [vid for vid in (vacancy_id or []) if vid is not None]
    if vacancy_ids:
        vacancy_subq = (
            select(1)
            .where(
                cvr_alias.candidate_id == Candidate.id,
                cvr_alias.vacancy_id.in_(vacancy_ids),
                cvr_alias.is_active.is_(True)
            )
            .correlate(Candidate)
        )
        query = query.where(exists(vacancy_subq))

    if role_id:
        role_str = str(role_id).strip()
        role_subq = (
            select(1)
            .select_from(cvr_alias)
            .join(Vacancy, Vacancy.id == cvr_alias.vacancy_id)
            .where(
                cvr_alias.candidate_id == Candidate.id,
                cvr_alias.is_active.is_(True),
                Vacancy.professional_roles_id.contains([role_str]),
            )
            .correlate(Candidate)
        )
        query = query.where(exists(role_subq))
        
    if is_perfect_candidate is not None:
        if is_perfect_candidate:
            query = query.where(exists(perfect_subq))
        else:
            query = query.where(~exists(perfect_subq))

    # === СОРТИРОВКА ===
    query = query.order_by(
        latest_activity_subq.desc().nullslast(),
        Candidate.id.desc()
    )

    # === ПОДСЧЁТ TOTAL (без ORDER BY / тяжёлых SELECT-подзапросов) ===
    count_query = select(func.count()).select_from(
        query.order_by(None).with_only_columns(Candidate.id).subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # === ПАГИНАЦИЯ ===
    paginated_query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(paginated_query)
    
    candidates_with_flag = result.all()
    
    candidates = []
    for row in candidates_with_flag:
        candidate_obj = row[0]
        candidate_obj.is_perfect_candidate = row[1]
        candidate_obj.current_status = row[2]
        candidate_obj.last_vacancy_id = row[3]
        candidate_obj.last_vacancy_title = row[4]
        _apply_telegram_fallback(candidate_obj, row[5])
        candidates.append(candidate_obj)

    total_pages = ceil(total / per_page)

    return PaginatedResponse(
        items=candidates,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.post('/candidate', response_model=CandidateRead, status_code=status.HTTP_200_OK)
async def post_candidate_endpoint(candidate_data: CandidateCreate,
                                  db: AsyncSession = Depends(get_db)):
    candidate = Candidate(**candidate_data.model_dump(exclude={'vacancy_id'}))
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.get('/candidate/{candidate_id}', response_model=CandidateRead)
async def get_candidate_endpoint(candidate_id: int, db: AsyncSession = Depends(get_db)):
    query = (
        select(Candidate)
        .options(
            selectinload(Candidate.vacancies).selectinload(CandidateVacancyRelation.vacancy),
            selectinload(Candidate.test_results),
            selectinload(Candidate.bot_user),
        )
        .where(Candidate.id == candidate_id, Candidate.archived_at.is_(None))
    )
    result = await db.execute(query)
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    bot_name = candidate.bot_user.name if candidate.bot_user else None
    _apply_telegram_fallback(candidate, bot_name)
    _attach_last_vacancy(candidate)
    return candidate


@router.patch('/candidate/{candidate_id}', response_model=CandidateRead)
async def update_candidate_endpoint(
    candidate_id: int,
    candidate_data: CandidateUpdate,
    db: AsyncSession = Depends(get_db),
):
    candidate = await db.get(Candidate, candidate_id)
    if not candidate or candidate.archived_at is not None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    update_data = candidate_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(candidate, field, value)

    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.delete('/candidate/{candidate_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate_endpoint(candidate_id: int, db: AsyncSession = Depends(get_db)):
    try:
        candidate = await db.get(Candidate, candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        if candidate.archived_at is not None:
            return None

        now = datetime.now(timezone.utc)
        previous_stage = str(candidate.stage)
        # Commit the essential operation first. Optional cleanup must never make
        # a successfully archived candidate look like a failed deletion.
        candidate.archived_at = now
        await db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception(f"Candidate archive failed for id={candidate_id}: {exc}")
        raise HTTPException(
            500,
            "Не удалось переместить кандидата в архив. Проверьте применение миграции candidate_archiving.sql",
        ) from exc

    try:
        # Operational cleanup is deliberately separated from the archive write:
        # legacy installations may not yet have every documents table.
        await db.execute(
            update(CandidateVacancyRelation)
            .where(
                CandidateVacancyRelation.candidate_id == candidate_id,
                CandidateVacancyRelation.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await db.execute(
            update(CandidateDocumentInvite)
            .where(
                CandidateDocumentInvite.candidate_id == candidate_id,
                CandidateDocumentInvite.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await db.execute(
            update(CandidateDocumentUploadSession)
            .where(
                CandidateDocumentUploadSession.candidate_id == candidate_id,
                CandidateDocumentUploadSession.status == "draft",
            )
            .values(status="expired", expires_at=now)
        )
        await write_audit(
            db,
            action="candidate.archive",
            entity_type="candidate",
            entity_id=candidate_id,
            details=f"Candidate archived from stage={previous_stage}",
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.warning(f"Candidate id={candidate_id} archived; optional cleanup failed: {exc}")
    return None


@router.post('/candidate/vacancy', response_model=ReadCandidateVacancyRelation, status_code=status.HTTP_200_OK)
async def post_candidate_to_vacancy_relation_endpoint(data: CreateCandidateVacancyRelation,
                                                          db: AsyncSession = Depends(get_db)):
    candidate = await db.get(Candidate, data.candidate_id)
    if not candidate or candidate.archived_at is not None:
        raise HTTPException(404, "Candidate not found")
    if not await db.get(Vacancy, data.vacancy_id):
        raise HTTPException(404, "Vacancy not found")
    if data.is_active:
        query = (
            select(CandidateVacancyRelation)
            .where((CandidateVacancyRelation.candidate_id == data.candidate_id) & (CandidateVacancyRelation.is_active == True))
        )
        result = await db.execute(query)
        active_vacancy = result.scalar_one_or_none()
        if active_vacancy:
            raise HTTPException(409, 'Already exists active vacancy')
    relation = CandidateVacancyRelation(**data.model_dump())
    db.add(relation)
    if data.is_active:
        candidate.stage = CandidateStage.employment
        from app.ai_eval.service import enqueue_candidate_evaluation

        await enqueue_candidate_evaluation(
            db,
            candidate_id=data.candidate_id,
            vacancy_id=data.vacancy_id,
            source="candidate.assigned",
        )
    await db.commit()

    result = await db.execute(
        select(CandidateVacancyRelation)
        .options(
            selectinload(CandidateVacancyRelation.candidate),
            selectinload(CandidateVacancyRelation.vacancy),
        )
        .where(CandidateVacancyRelation.id == relation.id)
    )
    return result.scalar_one()


@router.get('/candidate/{candidate_id}/active-vacancy', response_model=ReadVacancy)
async def get_active_vacancy_endpoint(candidate_id: int,
                                      db: AsyncSession = Depends(get_db)):
    query = (select(Vacancy)
             .join(CandidateVacancyRelation)
             .join(Candidate)
             .where((Candidate.id == candidate_id) & (CandidateVacancyRelation.is_active == True)))
    result = await db.execute(query)
    vacancy = result.scalar_one_or_none()
    if not vacancy:
        raise HTTPException(404, 'Vacancy not found')
    return vacancy


@router.get('/candidate/{relation_id}/vacancy', response_model=ReadCandidateVacancyRelation, status_code=status.HTTP_200_OK)
async def get_cnadidate_and_vacancy_endpoint(relation_id: int,
                                             db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CandidateVacancyRelation)
        .options(
            selectinload(CandidateVacancyRelation.candidate),
            selectinload(CandidateVacancyRelation.vacancy),
        )
        .where(CandidateVacancyRelation.id == relation_id)
    )
    relation = result.scalar_one_or_none()
    if not relation:
        raise HTTPException(404, 'Relation not found')
    return relation


@router.get('/candidate/{candidate_id}/vacancies', response_model=list[ReadCandidateVacancyRelation])
async def list_candidate_vacancies_endpoint(candidate_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CandidateVacancyRelation)
        .options(
            selectinload(CandidateVacancyRelation.candidate),
            selectinload(CandidateVacancyRelation.vacancy),
        )
        .where(CandidateVacancyRelation.candidate_id == candidate_id)
    )
    return result.scalars().all()


@router.patch('/candidate/vacancy/{relation_id}', response_model=ReadCandidateVacancyRelation)
async def update_candidate_vacancy_relation_endpoint(
    relation_id: int,
    data: CandidateVacancyRelationUpdate,
    db: AsyncSession = Depends(get_db),
):
    relation = await db.get(CandidateVacancyRelation, relation_id)
    if not relation:
        raise HTTPException(status_code=404, detail="Relation not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(relation, field, value)

    await db.commit()

    result = await db.execute(
        select(CandidateVacancyRelation)
        .options(
            selectinload(CandidateVacancyRelation.candidate),
            selectinload(CandidateVacancyRelation.vacancy),
        )
        .where(CandidateVacancyRelation.id == relation_id)
    )
    return result.scalar_one()


@router.delete('/candidate/vacancy/{relation_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate_vacancy_relation_endpoint(relation_id: int, db: AsyncSession = Depends(get_db)):
    relation = await db.get(CandidateVacancyRelation, relation_id)
    if not relation:
        raise HTTPException(status_code=404, detail="Relation not found")

    await db.delete(relation)
    await db.commit()
    return None


@router.get("/candidate/{candidate_id}/resume", status_code=status.HTTP_200_OK)
async def get_candidate_resume_endpoint(candidate_id: int, 
                               db: AsyncSession = Depends(get_db)) -> str:
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate not found")

    # собираем текст
    parts = []

    if candidate.full_name:
        parts.append(f"<b>ФИО:</b> {candidate.full_name}")
    if candidate.birth_date:
        parts.append(f"<b>Дата рождения:</b> {candidate.birth_date.strftime('%d.%m.%Y')}")
    if candidate.phone_number:
        parts.append(f"<b>Телефон:</b> {candidate.phone_number}")
    if getattr(candidate, "telegram_username", None):
        parts.append(f"<b>Telegram:</b> {candidate.telegram_username}")
    if getattr(candidate, "email", None):
        parts.append(f"<b>Почта:</b> {candidate.email}")
    if candidate.marital_status:
        parts.append(f"<b>Семейное положение:</b> {candidate.marital_status}")
    if candidate.hobbies:
        parts.append(f"<b>Хобби:</b> {', '.join(candidate.hobbies)}")
    if candidate.personal_characteristics:
        parts.append(f"<b>Личные качества:</b> {candidate.personal_characteristics}")

    if candidate.languages:
        parts.append(f"<b>Языки:</b> {', '.join(candidate.languages)}")
    if candidate.relevant_position_expirience:
        parts.append(f"<b>Опыт по релевантной должности:</b> {candidate.relevant_position_expirience}")
    if candidate.certain_position_expirience:
        parts.append(f"<b>Опыт по конкретной должности:</b> {candidate.certain_position_expirience}")
    if candidate.total_work_expirience:
        parts.append(f"<b>Общий опыт работы:</b> {candidate.total_work_expirience}")
    if candidate.other_work_expirience:
        parts.append(f"<b>Другой опыт работы:</b> {', '.join(candidate.other_work_expirience)}")
    if candidate.education:
        parts.append(f"<b>Образование:</b> {candidate.education}")
    if candidate.hard_skills:
        parts.append(f"<b>Hard skills:</b> {', '.join(candidate.hard_skills)}")
    if candidate.work_programs:
        parts.append(f"<b>Рабочие программы:</b> {', '.join(candidate.work_programs)}")
    if candidate.salary_expectations:
        parts.append(f"<b>Желаемая зарплата:</b> {candidate.salary_expectations} ₽")

    return "\n".join(parts)


from sqlalchemy.orm import selectinload

@router.get("/candidate/{candidate_id}/results", response_model=list[CandidatTestResultRead])
async def list_results_for_candidate_endpoint(candidate_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CandidateTestResult)
        .options(
            selectinload(CandidateTestResult.answers)
                .selectinload(CandidateQuestionAnswer.question),
            selectinload(CandidateTestResult.test)
        )
        .where(CandidateTestResult.candidate_id == candidate_id)
    )
    results = result.scalars().all()

    if not results:
        raise HTTPException(status_code=404, detail="No results found for this candidate")

    return results


#=====================================
#       Candidate Status
#=====================================
@router.get('/candidate/{candidate_id}/status', response_model=CandidateStatusSchema)
async def get_candidate_status_endpoint(candidate_id: int, db: AsyncSession = Depends(get_db)):
    query = (
        select(CandidateVacancyRelation)
        .where((CandidateVacancyRelation.candidate_id == candidate_id) & (CandidateVacancyRelation.is_active == True))
    )
    result = await db.execute(query)
    active_relation = result.scalar_one_or_none()
    if not active_relation:
        latest_result = await db.execute(
            select(CandidateVacancyRelation)
            .where(CandidateVacancyRelation.candidate_id == candidate_id)
            .order_by(
                desc(CandidateVacancyRelation.status_updated_at),
                desc(CandidateVacancyRelation.updated_at),
                desc(CandidateVacancyRelation.created_at),
                desc(CandidateVacancyRelation.id),
            )
        )
        active_relation = latest_result.scalars().first()
        if not active_relation:
            raise HTTPException(status_code=404, detail="Vacancy relation not found for this candidate")
    
    return {"status": active_relation.status}


@router.put('/candidate/{candidate_id}/status', response_model=CandidateStatusSchema)
async def update_candidate_status_endpoint(
    candidate_id: int,
    new_status: CandidateStatusSchema,
    db: AsyncSession = Depends(get_db),
    actor: tuple[Optional[str], Optional[str]] = Depends(actor_from_headers),
):
    from app.utils.audit import record_stage_change, write_audit
    from app.db.v1.enums import ARCHIVE_STATUSES
    from app.candidates.statuses import validate_status_transition

    actor_id, actor_name = actor

    query = (
        select(CandidateVacancyRelation)
        .where((CandidateVacancyRelation.candidate_id == candidate_id) & (CandidateVacancyRelation.is_active == True))
    )

    result = await db.execute(query)
    active_relation: CandidateVacancyRelation | None = result.scalar_one_or_none()
    if not active_relation:
        if new_status.status in ARCHIVE_STATUSES:
            raise HTTPException(status_code=404, detail="Active vacancy not found for this candidate")

        latest_result = await db.execute(
            select(CandidateVacancyRelation)
            .where(CandidateVacancyRelation.candidate_id == candidate_id)
            .order_by(
                desc(CandidateVacancyRelation.status_updated_at),
                desc(CandidateVacancyRelation.updated_at),
                desc(CandidateVacancyRelation.created_at),
                desc(CandidateVacancyRelation.id),
            )
        )
        active_relation = latest_result.scalars().first()
        if not active_relation:
            raise HTTPException(status_code=404, detail="Vacancy relation not found for this candidate")
        # Candidate can return from archive statuses back to funnel;
        # re-activate latest relation for further status transitions.
        active_relation.is_active = True

    try:
        validate_status_transition(active_relation.status, new_status.status)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if new_status.status == CandidateStatus.started_work:
        await hire_candidate_endpoint(candidate_id, db, actor)
        return {"status": CandidateStatus.started_work}

    old_status = active_relation.status
    active_relation.status = new_status.status
    active_relation.status_updated_at = datetime.now(timezone.utc)

    # Side-effects: terminal funnel statuses update candidate stage
    candidate = await db.get(Candidate, candidate_id)
    old_stage = candidate.stage if candidate else None
    if candidate and new_status.status in ARCHIVE_STATUSES:
        candidate.stage = CandidateStage.archieved
        active_relation.is_active = False
        if new_status.status == CandidateStatus.resigned:
            from app.services.vnr import mark_vnr_left

            await mark_vnr_left(db, candidate_id)
    elif candidate and new_status.status not in ARCHIVE_STATUSES:
        if candidate.stage == CandidateStage.archieved:
            candidate.stage = CandidateStage.employment

    try:
        await db.commit()
    except (DataError, IntegrityError, ProgrammingError) as exc:
        await db.rollback()
        logger.exception("Failed to update status for candidate %s", candidate_id)
        orig = str(getattr(exc, "orig", exc))
        if "invalid input value for enum" in orig.lower() or "подумать" in orig:
            raise HTTPException(
                status_code=400,
                detail="Нельзя сохранить статус: в PostgreSQL enum candidatestatus нет этого значения (нужна миграция, в т.ч. «подумать»).",
            ) from exc
        raise HTTPException(status_code=500, detail="Не удалось сменить статус") from exc
    except Exception as exc:
        await db.rollback()
        logger.exception("Unexpected failure while updating status for candidate %s", candidate_id)
        raise HTTPException(status_code=500, detail="Не удалось сменить статус") from exc

    # Best-effort audit: must never break status change on prod if audit tables
    # are missing or not migrated yet.
    try:
        await record_stage_change(
            db,
            candidate_id=candidate_id,
            from_stage=old_stage,
            to_stage=candidate.stage if candidate else None,
            from_status=old_status,
            to_status=new_status.status,
            actor_id=actor_id,
            actor_name=actor_name,
            comment="Смена статуса",
        )
        await write_audit(
            db,
            action="candidate.status",
            entity_type="candidate",
            entity_id=candidate_id,
            actor_id=actor_id,
            actor_name=actor_name,
            details=f"{old_status} → {new_status.status}",
        )
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Audit write failed for candidate status change %s", candidate_id)

    status_val = getattr(new_status.status, "value", new_status.status)
    if status_val == CandidateStatus.consider.value:
        try:
            hh = await get_hh_client()
            await sync_candidate_hh_action(hh, candidate_id, "consider")
        except Exception:
            logger.exception("HH consider sync failed for candidate %s", candidate_id)

    return {"status": new_status.status}


#=====================================
#       Candidate Stage
#=====================================

@router.get('/candidates/archived', response_model=list[CandidateRead])
async def get_archived_candidates_endpoint(db: AsyncSession = Depends(get_db)):
    query = (
        select(Candidate)
        .where(Candidate.stage == CandidateStage.archieved)
    )
    result = await db.execute(query)
    candidates = result.scalars().all()
    return candidates


@router.put('/candidate/{candidate_id}/archive', response_model=CandidateRead)
async def archive_candidate_endpoint(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    actor: tuple[Optional[str], Optional[str]] = Depends(actor_from_headers),
):
    from app.utils.audit import record_stage_change, write_audit

    actor_id, actor_name = actor

    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, 'Candidate not found')
    old_stage = candidate.stage
    candidate.stage = CandidateStage.archieved

    query = (
        select(CandidateVacancyRelation)
        .where((CandidateVacancyRelation.candidate_id == candidate_id) & (CandidateVacancyRelation.is_active == True))
    )
    result = await db.execute(query)
    relation: CandidateVacancyRelation | None = result.scalars().first()
    old_status = relation.status if relation else None
    if relation:
        relation.status = CandidateStatus.rejection
        relation.is_active = False

    await record_stage_change(
        db,
        candidate_id=candidate_id,
        from_stage=old_stage,
        to_stage=CandidateStage.archieved,
        from_status=old_status,
        to_status=CandidateStatus.rejection if relation else None,
        actor_id=actor_id,
        actor_name=actor_name,
        comment="Переведён в архив",
    )
    await write_audit(
        db,
        action="candidate.archive",
        entity_type="candidate",
        entity_id=candidate_id,
        actor_id=actor_id,
        actor_name=actor_name,
    )
    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.get('/candidates/blacklisted', response_model=list[CandidateRead])
async def get_blacklisted_candidates_endpoint(db: AsyncSession = Depends(get_db)):
    query = (
        select(Candidate)
        .where(Candidate.stage == CandidateStage.blacklisted)
    )
    result = await db.execute(query)
    candidates = result.scalars().all()
    return candidates


@router.put('/candidate/{candidate_id}/blacklist', response_model=CandidateRead)
async def blacklist_candidate_endpoint(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    actor: tuple[Optional[str], Optional[str]] = Depends(actor_from_headers),
):
    from app.utils.audit import record_stage_change, write_audit

    actor_id, actor_name = actor

    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, 'Candidate not found')
    old_stage = candidate.stage
    candidate.stage = CandidateStage.blacklisted

    query = (
        select(CandidateVacancyRelation)
        .where((CandidateVacancyRelation.candidate_id == candidate_id) & (CandidateVacancyRelation.is_active == True))
    )
    result = await db.execute(query)
    relation: CandidateVacancyRelation | None = result.scalars().first()
    old_status = relation.status if relation else None
    if relation:
        relation.status = CandidateStatus.not_suitable
        relation.is_active = False

    await record_stage_change(
        db,
        candidate_id=candidate_id,
        from_stage=old_stage,
        to_stage=CandidateStage.blacklisted,
        from_status=old_status,
        to_status=CandidateStatus.not_suitable if relation else None,
        actor_id=actor_id,
        actor_name=actor_name,
        comment="Добавлен в чёрный список",
    )
    await write_audit(
        db,
        action="candidate.blacklist",
        entity_type="candidate",
        entity_id=candidate_id,
        actor_id=actor_id,
        actor_name=actor_name,
    )
    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.put('/candidate/{candidate_id}/unblacklist', response_model=CandidateRead)
async def unblacklist_candidate_endpoint(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    actor: tuple[Optional[str], Optional[str]] = Depends(actor_from_headers),
):
    """
    Переносит кандидата из черного списка в архив.
    """
    from app.utils.audit import record_stage_change, write_audit

    actor_id, actor_name = actor
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, 'Candidate not found')
    old_stage = candidate.stage
    candidate.stage = CandidateStage.archieved
    await record_stage_change(
        db,
        candidate_id=candidate_id,
        from_stage=old_stage,
        to_stage=CandidateStage.archieved,
        actor_id=actor_id,
        actor_name=actor_name,
        comment="Убран из чёрного списка, переведён в архив",
    )
    await write_audit(
        db,
        action="candidate.unblacklist",
        entity_type="candidate",
        entity_id=candidate_id,
        actor_id=actor_id,
        actor_name=actor_name,
    )
    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.put('/candidate/{candidate_id}/hire', response_model=CandidateRead)
async def hire_candidate_endpoint(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    actor: tuple[Optional[str], Optional[str]] = Depends(actor_from_headers),
):
    """Mark candidate hired and create Employee record (idempotent)."""
    from app.db.v1.models import Employee
    from app.services.hr_lifecycle import employee_from_candidate
    from app.services.vnr import record_vnr_hire
    from app.utils.audit import record_stage_change, write_audit

    actor_id, actor_name = actor
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, 'Candidate not found')

    try:
        old_stage = candidate.stage
        candidate.stage = CandidateStage.hired

        query = (
            select(CandidateVacancyRelation)
            .where(
                (CandidateVacancyRelation.candidate_id == candidate_id)
                & (CandidateVacancyRelation.is_active == True)
            )
        )
        result = await db.execute(query)
        relation: CandidateVacancyRelation | None = result.scalars().first()
        if not relation:
            # Fallback: any relation for this candidate
            result = await db.execute(
                select(CandidateVacancyRelation).where(
                    CandidateVacancyRelation.candidate_id == candidate_id
                )
            )
            relation = result.scalars().first()
        if not relation:
            raise HTTPException(404, 'Active vacancy for this candidate not found')

        old_status = relation.status
        relation.status = CandidateStatus.started_work
        relation.is_active = False

        vacancy = await db.get(Vacancy, relation.vacancy_id)

        # Idempotent: reuse existing employee for this candidate (explicit query, no lazy load)
        emp_q = await db.execute(
            select(Employee).where(Employee.candidate_id == candidate_id)
        )
        existing_emp = emp_q.scalars().first()

        emp = existing_emp
        if existing_emp is None:
            # Avoid unique user_id collision if another employee already owns this bot user
            emp = employee_from_candidate(candidate, vacancy=vacancy)
            if candidate.user_id:
                clash = await db.execute(
                    select(Employee).where(Employee.user_id == candidate.user_id)
                )
                if clash.scalars().first():
                    emp.user_id = None
            db.add(emp)
            await db.flush()
            from app.adaptation.onboarding import enroll_new_employee
            enroll_new_employee(db, emp)

        await record_vnr_hire(
            db,
            candidate=candidate,
            vacancy=vacancy,
            employee=emp,
            actor_id=actor_id,
            actor_name=actor_name,
        )

        await record_stage_change(
            db,
            candidate_id=candidate_id,
            from_stage=old_stage,
            to_stage=CandidateStage.hired,
            from_status=old_status,
            to_status=CandidateStatus.started_work,
            actor_id=actor_id,
            actor_name=actor_name,
            comment="Оформлен на работу",
        )
        await write_audit(
            db,
            action="candidate.hire",
            entity_type="candidate",
            entity_id=candidate_id,
            actor_id=actor_id,
            actor_name=actor_name,
            details=f"vacancy_id={relation.vacancy_id}",
        )

        await db.commit()
        await db.refresh(candidate)
        return candidate
    except HTTPException:
        raise
    except (DataError, IntegrityError, ProgrammingError) as exc:
        await db.rollback()
        logger.exception("Failed to hire candidate %s (VNR)", candidate_id)
        orig = str(getattr(exc, "orig", exc)).lower()
        if "invalid input value for enum" in orig:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Нельзя оформить ВНР: в PostgreSQL нет нужного значения enum "
                    "(статус «ВНР» или стадия hired/нанят). Перезапустите database-service "
                    "после обновления — при старте метки добавляются сами."
                ),
            ) from exc
        if "vnr_hires" in orig and ("does not exist" in orig or "undefinedtable" in orig):
            raise HTTPException(
                status_code=500,
                detail="Не удалось оформить ВНР: нет таблицы vnr_hires. Перезапустите database-service.",
            ) from exc
        raise HTTPException(status_code=500, detail="Не удалось оформить кандидата на работу (ВНР)") from exc
    except Exception as exc:
        await db.rollback()
        logger.exception("Unexpected failure while hiring candidate %s", candidate_id)
        raise HTTPException(status_code=500, detail="Не удалось оформить кандидата на работу (ВНР)") from exc


@router.post('/candidate/fill-info', response_model=CandidateRead)
async def candidate_fill_info(
    data: CandidateFillInfoSchema,
    hh: Optional[APICLient] = Depends(get_hh_client),
    ai: Optional[APICLient] = Depends(get_ai_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Заполняет поля, генерируемые ai
    """
    if hh is None:
        raise HTTPException(503, "HH service is not configured")
    if ai is None:
        raise HTTPException(503, "AI service is not configured")

    query = (
        select(Vacancy)
        .join(CandidateVacancyRelation)
        .where(
            CandidateVacancyRelation.candidate_id == data.candidate_id,
            CandidateVacancyRelation.is_active == True
        )
    )
    result = await db.execute(query)
    vacancy: Vacancy | None = result.scalar_one_or_none()
    if not vacancy:
        raise HTTPException(404, 'Vacancy for this candidate not found')

    candidate_summary = await generate_candidate_summary(data.candidate_id, db)
    vacancy_summary = await generate_vacancy_description(vacancy.id, hh, db)
    company_image_summary = await get_company_candidate_image(db)
    department_image_summary = await get_department_candidate_image(vacancy.department, db)

    json = {
        "candidate_summary": candidate_summary,
        "vacancy_summary": vacancy_summary,
        "company_candidate_image": company_image_summary,
        "department_candidate_image": department_image_summary
    }
    ai_data = await ai.post(
        url_template='/candidate/evaluate',
        json=json
    )
    if not ai_data:
        raise HTTPException(500, 'AI Service is not available')

    candidate = await db.get(Candidate, data.candidate_id)
    if not candidate:
        raise HTTPException(404, 'Candidate not found')
    
    candidate.ai_comment = ai_data['comment']
    candidate.ai_score = ai_data['score']

    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.get('/candidate/{candidate_id}/info/html', response_model=CandidateHTMLResponse)
async def get_candidate_info_html_endpoint(
    candidate_id: int,
    db: AsyncSession = Depends(get_db)
):
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, 'Candidate not found')
    if candidate.ai_comment is None or candidate.ai_score is None:
        raise HTTPException(409, 'Fields ai_comment and ai_score must be not None')
    
    query = (
        select(Vacancy)
        .join(CandidateVacancyRelation)
        .where(
            CandidateVacancyRelation.candidate_id == candidate.id,
            CandidateVacancyRelation.is_active == True
        )
    )
    result = await db.execute(query)
    vacancy = result.scalar_one_or_none()
    if not vacancy:
        raise HTTPException(404, 'Vacancy for this candidate not found')
    
    html = render_candidate_html_for_telegram(candidate, vacancy)
    return {"text": html}


@router.get('/candidate/{candidate_id}/telegram', response_model=BotUserRead)
async def get_bot_user_by_candidate_endpoint(
    candidate_id: int, 
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(BotUser)
        .join(Candidate)
        .where(Candidate.id == candidate_id)
    )
    result = await db.execute(query)
    bot_user = result.scalar_one_or_none()
    if not bot_user:
        raise HTTPException(404, 'BotUser not found')
    return bot_user


@router.post('/candidate/vacancy/change', response_model=ReadCandidateVacancyRelation)
async def change_vacancy_endpoint(
    data: ChangeVacancyData,
    db: AsyncSession = Depends(get_db)
):
    try:
        candidate = await db.get(Candidate, data.candidate_id)
        if not candidate:
            raise HTTPException(404, "Candidate not found")
        vacancy = await db.get(Vacancy, data.vacancy_id)
        if not vacancy:
            raise HTTPException(404, "Vacancy not found")

        query = (
            select(CandidateVacancyRelation)
            .where(
                CandidateVacancyRelation.is_active == True,
                CandidateVacancyRelation.candidate_id == data.candidate_id
            )
        )
        result = await db.execute(query)
        rel: CandidateVacancyRelation | None = result.scalar_one_or_none()
        if rel and rel.vacancy_id == data.vacancy_id:
            raise HTTPException(409, "Candidate is already assigned to this vacancy")
        if rel:
            rel.is_active = False
        new_rel = CandidateVacancyRelation(
            is_active = True,
            candidate_id = data.candidate_id,
            status = CandidateStatus.applied,
            vacancy_id = data.vacancy_id
        )
        db.add(new_rel)
        candidate.stage = CandidateStage.employment
        from app.ai_eval.service import enqueue_candidate_evaluation

        await enqueue_candidate_evaluation(
            db,
            candidate_id=data.candidate_id,
            vacancy_id=data.vacancy_id,
            source="candidate.vacancy_changed",
        )
        await db.commit()
        await db.refresh(new_rel)
        return new_rel
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing vacancy: {str(e)}")
        await db.rollback()
        raise HTTPException(500, f'Error changing vacancy: {str(e)}')
