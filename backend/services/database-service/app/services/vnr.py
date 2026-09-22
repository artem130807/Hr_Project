"""VNR (вышел на работу) placements attributed to the hiring HR user."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.v1.enums import VnrHireStatus
from app.db.v1.models import Candidate, Employee, HrAvailability, Vacancy, VnrHire
from app.events.expiry import calendar_today


def _clip(value: str | None, size: int) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    return text[:size]


def _dept_name(vacancy: Vacancy | None) -> str | None:
    dept = getattr(vacancy, "department", None) if vacancy is not None else None
    if dept is None:
        return None
    return str(getattr(dept, "value", dept))


def _position_name(vacancy: Vacancy | None) -> str | None:
    if vacancy is None:
        return None
    name = getattr(vacancy, "name", None)
    return str(name) if name else None


async def record_vnr_hire(
    db: AsyncSession,
    *,
    candidate: Candidate,
    vacancy: Vacancy | None = None,
    employee: Employee | None = None,
    actor_id: str | None = None,
    actor_name: str | None = None,
) -> Optional[VnrHire]:
    """Idempotent: one VNR row per candidate, owned by the HR who hired them.

    First attribution wins. After the person leaves, a later hire reassigns
    the row to the new HR. Missing actor (e.g. bot) skips the row so a later
    HR ``/hire`` can still attach attribution.
    """
    hr_id = _clip(actor_id, 36)
    if not hr_id:
        return None

    result = await db.execute(
        select(VnrHire).where(VnrHire.candidate_id == candidate.id)
    )
    existing = result.scalars().first()
    now = datetime.now(timezone.utc)
    emp_id = getattr(employee, "id", None) if employee is not None else None
    full_name = (candidate.full_name or "").strip() or f"Кандидат #{candidate.id}"
    department = _dept_name(vacancy)
    position = _position_name(vacancy)
    hr_name = _clip(actor_name, 200)

    if existing:
        if existing.status == VnrHireStatus.left.value:
            existing.hr_user_id = hr_id
            existing.hr_user_name = hr_name
            existing.status = VnrHireStatus.in_work.value
            existing.left_at = None
            existing.hired_at = now
            if vacancy is not None:
                existing.vacancy_id = vacancy.id
            existing.full_name = full_name
            if department:
                existing.department = department
            if position:
                existing.position = position
        elif not existing.hr_user_id:
            existing.hr_user_id = hr_id
            existing.hr_user_name = hr_name
        if emp_id and not existing.employee_id:
            existing.employee_id = emp_id
        return existing

    row = VnrHire(
        hr_user_id=hr_id,
        hr_user_name=hr_name,
        candidate_id=candidate.id,
        employee_id=emp_id,
        vacancy_id=getattr(vacancy, "id", None) if vacancy is not None else None,
        full_name=full_name,
        department=department,
        position=position,
        hired_at=now,
        status=VnrHireStatus.in_work.value,
    )
    db.add(row)
    await db.flush()
    return row


async def mark_vnr_left(db: AsyncSession, candidate_id: int) -> Optional[VnrHire]:
    result = await db.execute(
        select(VnrHire).where(VnrHire.candidate_id == int(candidate_id))
    )
    row = result.scalars().first()
    if row is None:
        return None
    if row.status != VnrHireStatus.left.value:
        row.status = VnrHireStatus.left.value
        row.left_at = datetime.now(timezone.utc)
    return row


async def list_vnr_hires(
    db: AsyncSession,
    *,
    hr_user_id: str | None = None,
    active_only: bool = True,
) -> list[VnrHire]:
    q = select(VnrHire).order_by(VnrHire.hired_at.desc(), VnrHire.id.desc())
    hid = _clip(hr_user_id, 36)
    if hid:
        q = q.where(VnrHire.hr_user_id == hid)
    if active_only:
        q = q.where(VnrHire.status == VnrHireStatus.in_work.value)
    result = await db.execute(q)
    return list(result.scalars().all())


def interview_week_bounds(today: date | None = None) -> tuple[date, date]:
    """Monday–Sunday of the current week in Europe/Samara."""
    day = today or calendar_today()
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def _booked_interview_filter(hr_user_id: str):
    return (
        HrAvailability.hr_id == hr_user_id,
        HrAvailability.is_booked.is_(True),
        HrAvailability.candidate_id.is_not(None),
    )


async def hr_vnr_stats(db: AsyncSession, hr_user_id: str) -> dict[str, Any]:
    hid = _clip(hr_user_id, 36) or ""
    hired_q = await db.execute(
        select(func.count())
        .select_from(VnrHire)
        .where(VnrHire.hr_user_id == hid)
    )
    in_work_q = await db.execute(
        select(func.count())
        .select_from(VnrHire)
        .where(
            VnrHire.hr_user_id == hid,
            VnrHire.status == VnrHireStatus.in_work.value,
        )
    )
    booked = _booked_interview_filter(hid)
    interviews_q = await db.execute(
        select(func.count()).select_from(HrAvailability).where(*booked)
    )
    week_start, week_end = interview_week_bounds()
    week_q = await db.execute(
        select(func.count())
        .select_from(HrAvailability)
        .where(
            *booked,
            HrAvailability.date >= week_start,
            HrAvailability.date <= week_end,
        )
    )
    return {
        "hr_user_id": hid,
        "hired": int(hired_q.scalar() or 0),
        "in_work": int(in_work_q.scalar() or 0),
        "interviews": int(interviews_q.scalar() or 0),
        "interviews_this_week": int(week_q.scalar() or 0),
    }
