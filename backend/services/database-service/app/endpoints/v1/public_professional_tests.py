"""Public take + HR list for platform professional (Q&A) tests — standalone results."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.app_logging import logger
from app.db.middleware import get_db
from datetime import date

from app.db.v1.enums import CandidateStatus, TestType
from app.db.v1.models import (
    Candidate,
    CandidateQuestionAnswer,
    CandidateTestResult,
    CandidateVacancyRelation,
    PublicTestResult,
    Test,
    Vacancy,
)
from app.schemas.v1.public_professional_tests import (
    PublicTestResultListItem,
    PublicTestResultRead,
    PublicTestResultSubmit,
)
from app.services.professional_test_scoring import (
    normalize_public_answers,
    professional_test_passed,
    public_question_dto,
)
from app.utils.candidate_funnel import set_candidate_vacancy_status

public_router = APIRouter()
router = APIRouter()

QA_TYPE = TestType.questions


async def _load_qa_test(test_id: int, db: AsyncSession) -> Test:
    result = await db.execute(
        select(Test).options(selectinload(Test.questions)).where(Test.id == test_id)
    )
    test = result.scalar_one_or_none()
    if not test or test.test_type != QA_TYPE:
        raise HTTPException(404, "Test not found")
    return test


async def _identity_from_candidate(db: AsyncSession, candidate_id: int) -> tuple[str, str]:
    cand = await db.get(Candidate, int(candidate_id))
    full_name = ((cand.full_name if cand else None) or "Кандидат").strip()
    position = "—"
    found = await db.execute(
        select(CandidateVacancyRelation).where(
            (CandidateVacancyRelation.candidate_id == int(candidate_id))
            & (CandidateVacancyRelation.is_active == True)  # noqa: E712
        )
    )
    rel = found.scalar_one_or_none()
    if rel is None:
        latest = await db.execute(
            select(CandidateVacancyRelation)
            .where(CandidateVacancyRelation.candidate_id == int(candidate_id))
            .order_by(
                desc(CandidateVacancyRelation.status_updated_at),
                desc(CandidateVacancyRelation.updated_at),
                desc(CandidateVacancyRelation.created_at),
                desc(CandidateVacancyRelation.id),
            )
        )
        rel = latest.scalars().first()
    if rel is not None:
        vac = await db.get(Vacancy, rel.vacancy_id)
        if vac and (vac.name or "").strip():
            position = vac.name.strip()
    return full_name, position


@public_router.get("/public/tests/{test_id}")
async def get_public_professional_test(test_id: int, db: AsyncSession = Depends(get_db)):
    test = await _load_qa_test(test_id, db)
    questions = sorted(test.questions or [], key=lambda q: q.id or 0)
    return {
        "id": test.id,
        "name": test.name,
        "description": test.description,
        "instruction": test.instruction_text,
        "duration_minutes": test.duration_minutes,
        "questions": [public_question_dto(q) for q in questions],
    }


@public_router.post(
    "/public/tests/results",
    response_model=PublicTestResultRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_public_professional_result(
    data: PublicTestResultSubmit,
    db: AsyncSession = Depends(get_db),
):
    test = await _load_qa_test(data.test_id, db)
    answers, score, max_score = normalize_public_answers(data.answers, list(test.questions or []))
    if not answers:
        raise HTTPException(400, "Нет ответов по вопросам этого теста")

    candidate_result: CandidateTestResult | None = None
    if data.result_id is not None:
        found = await db.execute(
            select(CandidateTestResult).where(
                CandidateTestResult.id == int(data.result_id),
                CandidateTestResult.test_id == int(test.id),
            )
        )
        candidate_result = found.scalar_one_or_none()
    elif data.candidate_id is not None:
        found = await db.execute(
            select(CandidateTestResult).where(
                CandidateTestResult.candidate_id == int(data.candidate_id),
                CandidateTestResult.test_id == int(test.id),
            )
        )
        candidate_result = found.scalar_one_or_none()

    if candidate_result is None and data.candidate_id is not None:
        candidate_result = CandidateTestResult(
            candidate_id=int(data.candidate_id),
            test_id=int(test.id),
        )
        db.add(candidate_result)
        await db.flush()

    full_name = (data.full_name or "").strip()
    position = (data.position or "").strip()
    taken_at = data.taken_at or date.today()
    if candidate_result is not None:
        auto_name, auto_position = await _identity_from_candidate(
            db, int(candidate_result.candidate_id)
        )
        full_name = full_name or auto_name
        position = position or auto_position

    if not full_name or not position:
        raise HTTPException(400, "ФИО, должность и дата обязательны")

    row = PublicTestResult(
        test_id=test.id,
        test_name=test.name,
        full_name=full_name,
        position=position,
        taken_at=taken_at,
        answers=answers,
        score=score if max_score else None,
        max_score=max_score if max_score else None,
        timed_out=bool(data.timed_out),
        integrity=data.integrity,
    )
    db.add(row)

    if candidate_result is not None:
        candidate_result.score = score if max_score else None
        candidate_result.comment = (
            f"Автообновлено после прохождения теста {taken_at.isoformat()}"
        )
        candidate_result.has_image = False

        candidate_id_for_answers = int(candidate_result.candidate_id)
        for qid, payload in answers.items():
            try:
                question_id = int(qid)
            except (TypeError, ValueError):
                continue
            found_answer = await db.execute(
                select(CandidateQuestionAnswer).where(
                    CandidateQuestionAnswer.candidate_id == candidate_id_for_answers,
                    CandidateQuestionAnswer.question_id == question_id,
                )
            )
            answer_row = found_answer.scalar_one_or_none()
            if answer_row is None:
                answer_row = CandidateQuestionAnswer(
                    candidate_id=candidate_id_for_answers,
                    question_id=question_id,
                )
                db.add(answer_row)
            answer_row.result_id = candidate_result.id
            answer_row.answer_text = payload.get("value")
            is_correct = payload.get("is_correct")
            answer_row.answer_score = (
                1 if is_correct is True else 0 if is_correct is False else None
            )

        passed = professional_test_passed(
            score if max_score else None,
            max_score if max_score else None,
            timed_out=bool(data.timed_out),
        )
        funnel_status = (
            CandidateStatus.test_passed if passed else CandidateStatus.test_failed
        )
        updated = await set_candidate_vacancy_status(
            db, candidate_id_for_answers, funnel_status
        )
        if not updated:
            logger.warning(
                "Professional test finished for candidate %s but vacancy relation is missing",
                candidate_id_for_answers,
            )

    await db.commit()
    await db.refresh(row)
    return row


@router.get("/public-test-results", response_model=list[PublicTestResultListItem])
async def list_public_professional_results(
    test_id: int | None = Query(None),
    q: str | None = Query(None, description="Search by full name"),
    position: str | None = Query(None, description="Filter by specialty / position"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(PublicTestResult).order_by(desc(PublicTestResult.created_at))
    if test_id is not None:
        stmt = stmt.where(PublicTestResult.test_id == test_id)
    if q and q.strip():
        stmt = stmt.where(PublicTestResult.full_name.ilike(f"%{q.strip()}%"))
    if position and position.strip():
        stmt = stmt.where(PublicTestResult.position.ilike(f"%{position.strip()}%"))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/public-test-results/{result_id}", response_model=PublicTestResultRead)
async def get_public_professional_result(result_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PublicTestResult).where(PublicTestResult.id == result_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Result not found")
    return row
