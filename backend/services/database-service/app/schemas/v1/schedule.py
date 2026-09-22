import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AvailabilityCreate(BaseModel):
    hr_id: str = Field(..., description="ERP UUID HR-менеджера")
    date: datetime.date = Field(..., description="Дата доступности")
    start_time: datetime.time = Field(..., description="Начало доступности (например, 10:00)")
    end_time: datetime.time = Field(..., description="Конец доступности (например, 16:00)")
    slot_length_minutes: int = Field(60, description="Длина слота в минутах (по умолчанию 60)")


class EnsureBookRequest(BaseModel):
    hr_id: str = Field(..., description="ERP UUID HR-менеджера")
    candidate_id: int
    date: datetime.date
    start_time: datetime.time
    end_time: Optional[datetime.time] = None


class AvailabilitySlot(BaseModel):
    id: int
    date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    is_booked: bool
    candidate_id: Optional[int] = None
    candidate_name: Optional[str] = None

    class Config:
        from_attributes = True


def _candidate_name_from_state(slot) -> Optional[str]:
    """
    Read candidate name without triggering SQLAlchemy lazy-load.
    Uses instance __dict__ only (populated by selectinload / tests).
    """
    try:
        state = object.__getattribute__(slot, "__dict__")
    except Exception:
        state = getattr(slot, "__dict__", {}) or {}

    cand = state.get("candidate")
    if cand is None:
        # Plain namespace used in unit tests
        cand = state.get("_candidate") if "_candidate" in state else None
        if cand is None and "candidate" in state:
            cand = state["candidate"]
    if cand is None:
        # SimpleNamespace / non-ORM: safe getattr only if attribute exists in __dict__
        if "candidate" in state:
            cand = state.get("candidate")
        else:
            return None
    if cand is None:
        return None
    return getattr(cand, "full_name", None)


def slot_to_read(slot) -> AvailabilitySlot:
    """Map ORM/plain slot → API DTO. Never touches unloaded relationships."""
    return AvailabilitySlot(
        id=slot.id,
        date=slot.date,
        start_time=slot.start_time,
        end_time=slot.end_time,
        is_booked=bool(slot.is_booked),
        candidate_id=slot.candidate_id,
        candidate_name=_candidate_name_from_state(slot),
    )


def slots_to_read(slots) -> list[AvailabilitySlot]:
    return [slot_to_read(s) for s in slots]
