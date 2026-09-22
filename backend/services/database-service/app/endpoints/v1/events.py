from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app_logging import logger
from app.config import ERP_BASE
from app.db.middleware import get_db
from app.db.v1.models import Event
from app.erp.client import ErpClient
from app.erp.mapper import search_erp_directory_users
from app.events.publisher import publish_hr_calendar_event
from app.events.recurrence import (
    first_notify_at,
    is_permanent,
    next_dispatch_after_initial,
)
from app.schemas.v1.events import EventCreate, EventRead, EventUpdate, ErpEmployeeSuggestion

router = APIRouter()

_TYPES_WITHOUT_EMPLOYEE_NAME = frozenset(
    {"work_anniversary", "other", "interview", "permanent"}
)


@router.get("/events/employees/search", response_model=list[ErpEmployeeSuggestion])
async def search_event_employees(
    q: str = Query(..., min_length=1, max_length=100, description="Подстрока ФИО / Telegram"),
    limit: int = Query(15, ge=1, le=50),
    by: str = Query(
        "name",
        pattern="^(name|telegram)$",
        description="name — поиск по ФИО; telegram — по tg_username из ERP",
    ),
):
    """Быстрый поиск сотрудников среди активных учёток ERP (ФИО или Telegram)."""
    if not ERP_BASE:
        raise HTTPException(status_code=503, detail="ERP_BASE is not configured")
    try:
        raw_users = await ErpClient().list_users()
    except Exception as exc:
        logger.exception(f"ERP employees search failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Failed to load users from ERP: {exc}") from exc

    return search_erp_directory_users(raw_users, query=q, limit=limit, by=by)


@router.get("/events", response_model=list[EventRead])
async def list_events(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Event).order_by(Event.event_date.asc()))
    return result.scalars().all()


@router.post("/events", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(data: EventCreate, db: AsyncSession = Depends(get_db)):
    payload = data.model_dump()
    if payload.get("type") in _TYPES_WITHOUT_EMPLOYEE_NAME:
        payload["employee_name"] = None
    event = Event(**payload)
    if is_permanent(event):
        # If the initial Rabbit publish fails, Huey retries at first_notify_at.
        event.next_dispatch_at = first_notify_at(
            event.event_date,
            event.remind_before,
            event.remind_at_time,
        )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    published = await publish_hr_calendar_event(event, occurrence="initial")
    if is_permanent(event):
        if published:
            event.last_dispatched_at = datetime.now(timezone.utc)
            event.next_dispatch_at = next_dispatch_after_initial(event)
        await db.commit()
        await db.refresh(event)
    return event


@router.patch("/events/{event_id}", response_model=EventRead)
async def update_event(event_id: int, data: EventUpdate, db: AsyncSession = Depends(get_db)):
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    if is_permanent(event) and (
        data.repeat_interval_count is not None
        or data.repeat_interval_unit is not None
        or data.event_date is not None
        or data.remind_before is not None
        or data.remind_at_time is not None
    ):
        event.next_dispatch_at = next_dispatch_after_initial(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: int, db: AsyncSession = Depends(get_db)):
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.delete(event)
    await db.commit()
    return None
