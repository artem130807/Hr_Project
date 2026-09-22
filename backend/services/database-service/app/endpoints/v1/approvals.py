from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.middleware import get_db
from app.db.v1.enums import CandidateStatus
from app.db.v1.models import Approval, Candidate, CandidateVacancyRelation, Vacancy
from app.schemas.v1.hr_ops import ApprovalCreate, ApprovalRead
from app.utils.audit import record_stage_change, write_audit

router = APIRouter()

_FUNNEL_STATUSES = {item.value for item in CandidateStatus}


@router.get("/approvals", response_model=list[ApprovalRead])
async def list_approvals(
    candidate_id: int | None = Query(None),
    vacancy_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Approval).order_by(Approval.id.desc())
    if candidate_id:
        q = q.where(Approval.candidate_id == candidate_id)
    if vacancy_id:
        q = q.where(Approval.vacancy_id == vacancy_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/approvals", response_model=ApprovalRead, status_code=status.HTTP_201_CREATED)
async def create_approval(data: ApprovalCreate, db: AsyncSession = Depends(get_db)):
    candidate = await db.get(Candidate, data.candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate not found")
    vacancy = await db.get(Vacancy, data.vacancy_id)
    if not vacancy:
        raise HTTPException(404, "Vacancy not found")

    approval = Approval(
        vacancy_id=data.vacancy_id,
        candidate_id=data.candidate_id,
        approver_id=data.approver_id,
        approver_name=data.approver_name,
        new_status=data.new_status,
        comments=data.comments or "",
    )
    db.add(approval)

    rel_q = await db.execute(
        select(CandidateVacancyRelation).where(
            CandidateVacancyRelation.candidate_id == data.candidate_id,
            CandidateVacancyRelation.vacancy_id == data.vacancy_id,
            CandidateVacancyRelation.is_active.is_(True),
        )
    )
    relation = rel_q.scalars().first()
    if not relation:
        raise HTTPException(
            409,
            "Нет активной связи кандидат↔вакансия — согласование невозможно",
        )

    old_status = relation.status
    funnel_status = data.new_status if data.new_status in _FUNNEL_STATUSES else None
    if funnel_status:
        relation.status = funnel_status
        comment = data.comments.strip() if data.comments else ""
        await record_stage_change(
            db,
            candidate_id=data.candidate_id,
            from_status=old_status,
            to_status=funnel_status,
            actor_id=data.approver_id,
            actor_name=data.approver_name,
            comment=comment or f"Согласование: {data.new_status}",
        )

    await write_audit(
        db,
        action="approval.create",
        entity_type="candidate",
        entity_id=data.candidate_id,
        actor_id=data.approver_id,
        actor_name=data.approver_name,
        details=f"decision={data.new_status} vacancy={data.vacancy_id}",
    )
    await db.commit()
    await db.refresh(approval)
    return approval
