from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.orm import selectinload

from app.db.v1.models import CandidateVacancyRelation, Candidate
from app.db.v1.enums import CandidateStatus
from app.clients.api_client import APICLient
from app.utils.ai import generate_candidate_summary, generate_vacancy_description, get_company_candidate_image, get_department_candidate_image
from app.config import time_to_consider_candidate_not_completed_tests
from app.app_logging import logger

statuses_before_test_completion = set(
    [
        CandidateStatus.cold_contact,
        CandidateStatus.applied,
        CandidateStatus.test_sent,
    ]
)

async def update_statuses_task(
        db: AsyncSession,
        ai: APICLient,
        hh: APICLient
):
    try:
        rels = await get_active_relations_candidate_not_completed_tests(db)
    except Exception as e:
        logger.error(f"Error fetching active relations: {e}")
        return

    for rel in rels:
        # Extract scalar values before any await — ORM objects can become expired
        # after async DB operations (MissingGreenlet in SQLAlchemy async context)
        rel_id = rel.id
        rel_candidate_id = rel.candidate_id
        rel_vacancy_id = rel.vacancy_id
        rel_vacancy_department = rel.vacancy.department if rel.vacancy else None

        try:
            ai_data = await get_ai_evaluation(
                ai=ai,
                db=db,
                hh=hh,
                candidate_id=rel_candidate_id,
                vacancy_id=rel_vacancy_id,
                vacancy_department=rel_vacancy_department,
            )
            await process_relation(db, rel_id, ai_data)
            # Явно коммитим изменения для этой записи
            await db.commit()
        except Exception as e:
            logger.error(f"Error processing relation for candidate {rel_candidate_id}: {e}")
            # Откатываем только текущую попытку
            await db.rollback()
            continue


async def process_relation(
        db: AsyncSession,
        rel_id: int,
        ai_data: dict
):
    fresh_rel = await db.get(CandidateVacancyRelation, rel_id)
    if (
        not fresh_rel
        or not fresh_rel.is_active
        or fresh_rel.status not in statuses_before_test_completion
        or fresh_rel.tests_not_completed
    ):
        candidate_id = fresh_rel.candidate_id if fresh_rel else "unknown"
        logger.info(f"Skipping candidate {candidate_id}: already processed or invalid state")
        return  # ← не коммитим, просто выходим

    logger.info(f"Marking candidate {fresh_rel.candidate_id} as tests_not_completed")

    candidate = await db.get(Candidate, fresh_rel.candidate_id)
    if not candidate:
        raise Exception("Candidate not found")

    try:
        score = float(ai_data['score'])
    except (TypeError, ValueError):
        score = 0.0

    candidate.ai_comment = str(ai_data.get('comment', ''))
    candidate.ai_score = score
    fresh_rel.tests_not_completed = True
    fresh_rel.perfect_candidate = score >= 80.0

    logger.info(f"Updated candidate {candidate.id}: score={score}, perfect={score >= 80.0}")
    # flush не обязателен — commit() сам сделает flush


async def get_active_relations_candidate_not_completed_tests(
        db: AsyncSession
) -> list[CandidateVacancyRelation]:
    now = datetime.now(timezone.utc)
    query = (
        select(CandidateVacancyRelation).
        where(
            and_(
            CandidateVacancyRelation.is_active == True,
            CandidateVacancyRelation.status.in_(statuses_before_test_completion),
            CandidateVacancyRelation.status_updated_at <= now - timedelta(minutes=time_to_consider_candidate_not_completed_tests)
            )
        )
        .options(
            selectinload(CandidateVacancyRelation.vacancy)
        )
    )
    result = await db.execute(query)
    rels = result.scalars().all()
    logger.info(f"Found cadidates: {len(rels)}")
    return rels


async def get_ai_evaluation(
        ai: APICLient,
        db: AsyncSession,
        hh: APICLient,
        candidate_id: int,
        vacancy_id: int,
        vacancy_department: str | None
) -> dict:
    candidate_summary = await generate_candidate_summary(candidate_id, db)
    vacancy_summary = await generate_vacancy_description(vacancy_id, hh, db)
    company_image_summary = await get_company_candidate_image(db)
    department_image_summary = await get_department_candidate_image(vacancy_department, db)
    
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
    if not ai_data or 'comment' not in ai_data or 'score' not in ai_data:
        raise Exception("Invalid AI response")
    logger.info(f"Evaluation score: {ai_data['score']}")
    return ai_data
