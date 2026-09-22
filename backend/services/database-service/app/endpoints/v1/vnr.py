from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.middleware import get_db
from app.schemas.v1.vnr import HrProfileStats, VnrHireRead
from app.services import vnr as vnr_svc
from app.utils.actor import actor_from_headers

router = APIRouter()


@router.get("/vnr-hires", response_model=list[VnrHireRead])
async def list_vnr_hires(
    hr_user_id: str | None = Query(None, description="ERP user id of the hiring HR"),
    active_only: bool = Query(True),
    mine: bool = Query(False, description="If true, filter by X-Actor-Id"),
    db: AsyncSession = Depends(get_db),
    actor: tuple[str | None, str | None] = Depends(actor_from_headers),
):
    actor_id, _ = actor
    target = hr_user_id
    if mine:
        target = (actor_id or "").strip() or hr_user_id
    rows = await vnr_svc.list_vnr_hires(
        db, hr_user_id=target, active_only=active_only
    )
    return rows


@router.get("/analytics/hr-profile", response_model=HrProfileStats)
async def get_hr_profile_stats(
    hr_user_id: str | None = Query(None, description="ERP user id; defaults to X-Actor-Id"),
    db: AsyncSession = Depends(get_db),
    actor: tuple[str | None, str | None] = Depends(actor_from_headers),
):
    """Per-HR stats for the profile page: собеседования, трудоустроенные, в работе."""
    actor_id, _ = actor
    target = (hr_user_id or actor_id or "").strip()
    if not target:
        raise HTTPException(400, "HR user id is required (header X-Actor-Id or query hr_user_id)")
    return await vnr_svc.hr_vnr_stats(db, target)
