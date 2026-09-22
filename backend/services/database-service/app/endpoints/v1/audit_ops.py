from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.middleware import get_db
from app.db.v1.models import AuditLog, Candidate, CandidateComment, CandidateStageHistory
from app.schemas.v1.hr_ops import (
    AuditLogRead,
    CandidateCommentCreate,
    CandidateCommentRead,
    StageHistoryRead,
)
from app.utils.audit import write_audit

router = APIRouter()


@router.get("/audit-logs", response_model=list[AuditLogRead])
async def list_audit_logs(
    entity_type: str | None = Query(None),
    entity_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.where(AuditLog.entity_id == entity_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/candidate/{candidate_id}/stage-history", response_model=list[StageHistoryRead])
async def list_stage_history(candidate_id: int, db: AsyncSession = Depends(get_db)):
    if not await db.get(Candidate, candidate_id):
        raise HTTPException(404, "Candidate not found")
    result = await db.execute(
        select(CandidateStageHistory)
        .where(CandidateStageHistory.candidate_id == candidate_id)
        .order_by(CandidateStageHistory.id.desc())
    )
    return result.scalars().all()


@router.get("/candidate/{candidate_id}/comments", response_model=list[CandidateCommentRead])
async def list_comments(candidate_id: int, db: AsyncSession = Depends(get_db)):
    if not await db.get(Candidate, candidate_id):
        raise HTTPException(404, "Candidate not found")
    result = await db.execute(
        select(CandidateComment)
        .where(CandidateComment.candidate_id == candidate_id)
        .order_by(CandidateComment.id.desc())
    )
    return result.scalars().all()


@router.post(
    "/candidate/{candidate_id}/comments",
    response_model=CandidateCommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    candidate_id: int,
    data: CandidateCommentCreate,
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(Candidate, candidate_id):
        raise HTTPException(404, "Candidate not found")
    row = CandidateComment(
        candidate_id=candidate_id,
        body=data.body.strip(),
        author_id=data.author_id,
        author_name=data.author_name,
    )
    db.add(row)
    await write_audit(
        db,
        action="candidate.comment",
        entity_type="candidate",
        entity_id=candidate_id,
        actor_id=data.author_id,
        actor_name=data.author_name,
        details=data.body[:500],
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.delete(
    "/candidate/{candidate_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment(
    candidate_id: int,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(CandidateComment, comment_id)
    if not row or row.candidate_id != candidate_id:
        raise HTTPException(404, "Comment not found")
    await db.delete(row)
    await db.commit()
    return None
