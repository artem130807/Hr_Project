from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.v1.enums import ARCHIVE_STATUSES, CandidateStatus
from app.db.v1.models import CandidateVacancyRelation


async def set_candidate_vacancy_status(
    db: AsyncSession,
    candidate_id: int,
    status: CandidateStatus,
) -> bool:
    """Update active vacancy funnel status. Returns False if candidate has no relation."""
    result = await db.execute(
        select(CandidateVacancyRelation).where(
            (CandidateVacancyRelation.candidate_id == int(candidate_id))
            & (CandidateVacancyRelation.is_active == True)  # noqa: E712
        ).order_by(
            desc(CandidateVacancyRelation.status_updated_at),
            desc(CandidateVacancyRelation.updated_at),
            desc(CandidateVacancyRelation.created_at),
            desc(CandidateVacancyRelation.id),
        )
    )
    # Historical data may contain more than one active relation. Select the
    # latest deterministically instead of failing the whole action with
    # MultipleResultsFound.
    rel = result.scalars().first()
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
        if rel is None:
            return False
        if status not in ARCHIVE_STATUSES:
            rel.is_active = True
    rel.status = status
    rel.status_updated_at = datetime.now(timezone.utc)
    return True
