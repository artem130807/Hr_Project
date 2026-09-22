from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Sequence
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.v1.models import CandidateAiEvaluation, OutboxMessage, Vacancy

EVENT_REQUEST = "hr.candidate.evaluate.requested"


async def enqueue_candidate_evaluation(
    db: AsyncSession,
    *,
    candidate_id: int,
    vacancy_id: Optional[int],
    source: str = "candidate.assigned",
) -> Optional[CandidateAiEvaluation]:
    """Insert evaluation + outbox row in the current transaction (caller commits)."""
    if not candidate_id or not vacancy_id:
        return None

    pending = (
        await db.execute(
            select(CandidateAiEvaluation).where(
                CandidateAiEvaluation.candidate_id == candidate_id,
                CandidateAiEvaluation.vacancy_id == vacancy_id,
                CandidateAiEvaluation.status == "pending",
            )
        )
    ).scalars().first()
    if pending is not None:
        return pending

    vacancy = await db.get(Vacancy, vacancy_id)
    department = None
    if vacancy is not None and getattr(vacancy, "department", None) is not None:
        department = getattr(vacancy.department, "value", vacancy.department)

    correlation_id = str(uuid4())
    evaluation = CandidateAiEvaluation(
        candidate_id=candidate_id,
        vacancy_id=vacancy_id,
        correlation_id=correlation_id,
        source=source,
        status="pending",
    )
    db.add(evaluation)
    await db.flush()

    payload: dict[str, Any] = {
        "event_type": EVENT_REQUEST,
        "correlation_id": correlation_id,
        "evaluation_id": evaluation.id,
        "candidate_id": candidate_id,
        "vacancy_id": vacancy_id,
        "department": department,
        "source": source,
    }
    db.add(
        OutboxMessage(
            event_type=EVENT_REQUEST,
            aggregate_type="candidate_evaluation",
            aggregate_id=str(evaluation.id),
            correlation_id=correlation_id,
            payload=payload,
            status="pending",
        )
    )
    return evaluation


async def list_pending_outbox(
    db: AsyncSession,
    *,
    limit: int = 25,
    event_type: str | None = EVENT_REQUEST,
) -> Sequence[OutboxMessage]:
    stmt = select(OutboxMessage).where(OutboxMessage.status == "pending")
    if event_type:
        stmt = stmt.where(OutboxMessage.event_type == event_type)
    result = await db.execute(stmt.order_by(OutboxMessage.id.asc()).limit(limit))
    return result.scalars().all()


async def mark_outbox_published(row: OutboxMessage) -> None:
    row.status = "published"
    row.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.last_error = None


async def mark_outbox_failed(row: OutboxMessage, error: str) -> None:
    row.attempts = int(row.attempts or 0) + 1
    row.last_error = (error or "")[:2000]
    if row.attempts >= 12:
        row.status = "failed"


async def apply_evaluation_result(db: AsyncSession, payload: dict[str, Any]) -> bool:
    from app.db.v1.models import Candidate

    correlation_id = str(payload.get("correlation_id") or "").strip()
    evaluation_id = payload.get("evaluation_id")
    row = None
    if evaluation_id not in (None, ""):
        try:
            row = await db.get(CandidateAiEvaluation, int(evaluation_id))
        except (TypeError, ValueError):
            row = None
    if row is None and correlation_id:
        row = (
            await db.execute(
                select(CandidateAiEvaluation).where(
                    CandidateAiEvaluation.correlation_id == correlation_id
                )
            )
        ).scalar_one_or_none()
    if row is None:
        return False
    if row.status == "completed":
        return True

    status = str(payload.get("status") or "completed")
    if status == "failed":
        row.status = "failed"
        row.error = str(payload.get("error") or "")[:2000]
        await db.commit()
        return True

    try:
        score = int(round(float(payload.get("score"))))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))
    comment = str(payload.get("comment") or "").strip()

    row.status = "completed"
    row.score = score
    row.comment = comment
    row.error = None

    candidate = await db.get(Candidate, row.candidate_id)
    if candidate is not None:
        candidate.ai_score = score
        candidate.ai_comment = comment

    await db.commit()
    return True
