from datetime import timedelta, datetime, date, time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, extract
from sqlalchemy.orm import selectinload

from app.db.middleware import get_db
from app.db.v1.models import HrAvailability
from app.schemas.v1.schedule import (
    AvailabilityCreate,
    AvailabilitySlot,
    EnsureBookRequest,
    slot_to_read,
    slots_to_read,
)


router = APIRouter()


def _slots_query():
    # Eager-load candidate so names are in instance state (no async lazy-load).
    return select(HrAvailability).options(selectinload(HrAvailability.candidate))


def _norm_time(value) -> time:
    if value is None:
        raise HTTPException(status_code=400, detail="start_time is required")
    return value.replace(second=0, microsecond=0)


async def _persist(db: AsyncSession, *, commit: bool) -> None:
    if commit:
        await db.commit()
    else:
        await db.flush()


async def ensure_and_book_slot(
    db: AsyncSession,
    *,
    hr_id: str,
    candidate_id: int,
    slot_date: date,
    start_time,
    end_time=None,
    commit: bool = True,
) -> AvailabilitySlot:
    """Find a slot at this datetime or create one, then book it for the candidate."""
    hr_key = str(hr_id or "").strip()
    if not hr_key:
        raise HTTPException(status_code=400, detail="hr_id is required")
    if len(hr_key) > 36:
        raise HTTPException(status_code=400, detail="hr_id is too long (max 36)")
    if not candidate_id:
        raise HTTPException(status_code=400, detail="candidate_id is required")

    start = _norm_time(start_time)
    if end_time is None:
        end = (datetime.combine(slot_date, start) + timedelta(hours=1)).time()
    else:
        end = _norm_time(end_time)
        if datetime.combine(slot_date, end) <= datetime.combine(slot_date, start):
            end = (datetime.combine(slot_date, start) + timedelta(hours=1)).time()

    existing = await db.execute(
        select(HrAvailability)
        .where(
            HrAvailability.hr_id == hr_key,
            HrAvailability.date == slot_date,
            extract("hour", HrAvailability.start_time) == start.hour,
            extract("minute", HrAvailability.start_time) == start.minute,
        )
        .order_by(HrAvailability.is_booked.asc(), HrAvailability.id.asc())
    )
    slots = list(existing.scalars().all())

    already_mine = next(
        (
            item
            for item in slots
            if item.is_booked and int(item.candidate_id or 0) == int(candidate_id)
        ),
        None,
    )
    if already_mine is not None:
        return slot_to_read(already_mine)

    slot = next((item for item in slots if not item.is_booked), None)
    if slot is None:
        if slots:
            raise HTTPException(status_code=400, detail="Slot already booked")
        slot = HrAvailability(
            hr_id=hr_key,
            date=slot_date,
            start_time=start,
            end_time=end,
            is_booked=True,
            candidate_id=int(candidate_id),
        )
        db.add(slot)
        try:
            await _persist(db, commit=commit)
        except HTTPException:
            raise
        except Exception as exc:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to book availability: {exc}") from exc
        await db.refresh(slot)
        return AvailabilitySlot(
            id=slot.id,
            date=slot.date,
            start_time=slot.start_time,
            end_time=slot.end_time,
            is_booked=True,
            candidate_id=int(candidate_id),
            candidate_name=None,
        )

    booked = await db.execute(
        update(HrAvailability)
        .where(HrAvailability.id == slot.id)
        .where(HrAvailability.is_booked == False)  # noqa: E712
        .values(is_booked=True, candidate_id=int(candidate_id))
    )
    if booked.rowcount == 0:
        raise HTTPException(status_code=400, detail="Slot already booked")
    await _persist(db, commit=commit)
    refreshed = await db.execute(_slots_query().where(HrAvailability.id == slot.id))
    row = refreshed.scalar_one()
    return slot_to_read(row)


@router.post("/availability/hr", response_model=list[AvailabilitySlot])
async def create_availability_slots_endpoint(
    data: AvailabilityCreate,
    db: AsyncSession = Depends(get_db),
):
    """Создать интервалы доступности для HR (например, 10:00–16:00 → 6 слотов по часу)"""

    start = datetime.combine(data.date, data.start_time)
    end = datetime.combine(data.date, data.end_time)

    if start >= end:
        raise HTTPException(status_code=400, detail="Invalid time range")

    hr_id = str(data.hr_id).strip()
    if not hr_id:
        raise HTTPException(status_code=400, detail="hr_id is required")
    if len(hr_id) > 36:
        raise HTTPException(status_code=400, detail="hr_id is too long (max 36)")

    slots = []
    delta = timedelta(minutes=data.slot_length_minutes)
    current = start

    while current + delta <= end:
        slot = HrAvailability(
            hr_id=hr_id,
            date=data.date,
            start_time=current.time(),
            end_time=(current + delta).time(),
            is_booked=False,
        )
        db.add(slot)
        slots.append(slot)
        current += delta

    if not slots:
        raise HTTPException(
            status_code=400,
            detail="Интервал слишком короткий для длины слота (нужен минимум 1 полный слот)",
        )

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save availability: {e}") from e

    for slot in slots:
        await db.refresh(slot)

    # Column-only DTOs — never touch relationships on freshly inserted rows.
    return [
        AvailabilitySlot(
            id=slot.id,
            date=slot.date,
            start_time=slot.start_time,
            end_time=slot.end_time,
            is_booked=False,
            candidate_id=None,
            candidate_name=None,
        )
        for slot in slots
    ]


@router.get("/availability/hr/{hr_id}", response_model=list[AvailabilitySlot])
async def get_hr_availability_endpoint(
    hr_id: str,
    date_from: date,
    date_to: date,
    db: AsyncSession = Depends(get_db),
):
    """Получить список доступных слотов HR за период"""
    query = (
        _slots_query()
        .where(
            HrAvailability.hr_id == str(hr_id).strip(),
            HrAvailability.date.between(date_from, date_to),
        )
        .order_by(HrAvailability.date, HrAvailability.start_time)
    )
    result = await db.scalars(query)
    return slots_to_read(result.all())


@router.post("/availability/book/{slot_id}/{candidate_id}")
async def book_slot_endpoint(
    slot_id: int,
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Забронировать слот кандидатом (атомарно, защита от двойного бронирования)."""
    result = await db.execute(
        update(HrAvailability)
        .where(HrAvailability.id == slot_id)
        .where(HrAvailability.is_booked == False)  # noqa: E712
        .values(is_booked=True, candidate_id=candidate_id)
    )
    if result.rowcount == 0:
        slot = await db.get(HrAvailability, slot_id)
        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")
        raise HTTPException(status_code=400, detail="Slot already booked")

    await db.commit()
    return {"message": "Slot booked", "slot_id": slot_id}


@router.post("/availability/ensure-book", response_model=AvailabilitySlot)
async def ensure_book_slot_endpoint(
    data: EnsureBookRequest,
    db: AsyncSession = Depends(get_db),
):
    """Создать слот, если его ещё нет, и забронировать его за кандидатом."""
    return await ensure_and_book_slot(
        db,
        hr_id=data.hr_id,
        candidate_id=data.candidate_id,
        slot_date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
    )


@router.post("/availability/unbook/{slot_id}", response_model=AvailabilitySlot)
async def unbook_slot_endpoint(
    slot_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Снять бронь со слота (вернуть в доступные)."""
    result = await db.execute(
        _slots_query().where(HrAvailability.id == slot_id)
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if not slot.is_booked:
        raise HTTPException(status_code=400, detail="Slot is not booked")

    slot.is_booked = False
    slot.candidate_id = None
    await db.commit()
    # Re-load without candidate relationship for safe DTO
    await db.refresh(slot)
    return AvailabilitySlot(
        id=slot.id,
        date=slot.date,
        start_time=slot.start_time,
        end_time=slot.end_time,
        is_booked=False,
        candidate_id=None,
        candidate_name=None,
    )


@router.delete("/availability/{slot_id}")
async def delete_slot_endpoint(
    slot_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Удалить слот полностью."""
    slot = await db.get(HrAvailability, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    await db.delete(slot)
    await db.commit()
    return {"message": "Slot deleted", "slot_id": slot_id}


@router.get("/availability/all", response_model=list[AvailabilitySlot])
async def get_all_availability_endpoint(
    date_from: date,
    date_to: date,
    db: AsyncSession = Depends(get_db),
):
    """Получить список доступных слотов всех HR за период."""
    query = (
        _slots_query()
        .where(
            and_(
                HrAvailability.date.between(date_from, date_to),
                HrAvailability.is_booked == False,  # noqa: E712
            )
        )
        .order_by(HrAvailability.date, HrAvailability.start_time)
    )
    result = await db.scalars(query)
    return slots_to_read(result.all())


@router.get("/availability/{slot_id}", response_model=AvailabilitySlot)
async def get_slot_endpoint(
    slot_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Получить информацию о конкретном слоте по ID."""
    result = await db.execute(_slots_query().where(HrAvailability.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    return slot_to_read(slot)
