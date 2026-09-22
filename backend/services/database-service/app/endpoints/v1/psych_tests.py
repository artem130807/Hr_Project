"""Public + HR APIs for standalone psychological instruments / results."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.middleware import get_db
from app.db.v1.models import PsychTestResult
from app.psychometrics.numerology import numerology_payload
from app.psychometrics.scoring import (
    list_instruments_meta,
    load_instrument,
    public_instrument_payload,
    score_instrument,
)
from app.schemas.v1.psych_tests import (
    PsychResultListItem,
    PsychResultRead,
    PsychResultSubmit,
)

public_router = APIRouter()
router = APIRouter()


@public_router.get("/public/psych/instruments")
async def list_public_instruments():
    return {"items": list_instruments_meta()}


@public_router.get("/public/psych/instruments/{instrument_id}")
async def get_public_instrument(instrument_id: str):
    try:
        return public_instrument_payload(instrument_id)
    except KeyError:
        raise HTTPException(404, "Instrument not found") from None


@public_router.post(
    "/public/psych/results",
    response_model=PsychResultRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_psych_result(
    data: PsychResultSubmit,
    db: AsyncSession = Depends(get_db),
):
    try:
        instrument = load_instrument(data.instrument_id)
    except KeyError:
        raise HTTPException(404, "Instrument not found") from None

    scores = score_instrument(data.answers, instrument, data.timing)
    numerology = numerology_payload(data.birth_date)
    scores["numerology"] = numerology
    summary = scores.get("summary") or {}
    quality = scores.get("quality") or {}
    row = PsychTestResult(
        instrument_id=instrument.get("id") or data.instrument_id,
        instrument_version=instrument.get("version"),
        full_name=data.full_name,
        position=data.position,
        taken_at=data.taken_at,
        birth_date=data.birth_date,
        chs=numerology["chs"],
        chm=numerology["chm"],
        answers=data.answers,
        scores=scores,
        quality_status=quality.get("status") or summary.get("quality_status"),
        leading_disc=summary.get("behavior_preference"),
        leading_paei=summary.get("management_focus"),
        leading_work10=summary.get("work_style_focus"),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/psych/instruments")
async def list_instruments_hr():
    """Same catalog for HR UI (authenticated)."""
    return {"items": list_instruments_meta()}


@router.get("/psych/results", response_model=list[PsychResultListItem])
async def list_psych_results(
    instrument_id: str | None = Query(None),
    q: str | None = Query(None, description="Search by full name"),
    position: str | None = Query(None, description="Filter by specialty / position"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(PsychTestResult).order_by(desc(PsychTestResult.created_at))
    if instrument_id:
        stmt = stmt.where(PsychTestResult.instrument_id == instrument_id)
    if q and q.strip():
        stmt = stmt.where(PsychTestResult.full_name.ilike(f"%{q.strip()}%"))
    if position and position.strip():
        stmt = stmt.where(PsychTestResult.position.ilike(f"%{position.strip()}%"))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/psych/results/{result_id}", response_model=PsychResultRead)
async def get_psych_result(result_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PsychTestResult).where(PsychTestResult.id == result_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Result not found")
    return row
