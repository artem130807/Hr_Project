"""Доменные события HR-календаря (публикация в RabbitMQ для message-service)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Any, ClassVar, Optional
from uuid import UUID, uuid4

from app.domain.domain_event import DomainEvent


def _remind_at_time_payload(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, time):
        return value.strftime("%H:%M")
    text = str(value).strip()
    return text or None


@dataclass(frozen=True)
class HrEventCreatedEvent(DomainEvent):
    """Событие: в HR создана запись календаря (день рождения, годовщина и т.п.)."""

    event_type: ClassVar[str] = "hr.event.created"

    hr_event_id: int
    type: str
    event_date: date
    remind_before: int = 3
    remind_at_time: Optional[str] = None  # "HH:MM" Samara local; None = ASAP on notify day
    employee_name: Optional[str] = None
    child_name: Optional[str] = None
    telegram_user: Optional[str] = None
    note: Optional[str] = None
    is_done: bool = False
    repeat_interval_count: Optional[int] = None
    repeat_interval_unit: Optional[str] = None
    occurrence: str = "initial"
    # ERP UUID получателя (по tg_username) — для message-service / личных сообщений.
    user_id: Optional[str] = None
    actor_user_id: Optional[str] = None
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def payload(self) -> dict[str, Any]:
        return {
            "hr_event_id": self.hr_event_id,
            "type": self.type,
            "employee_name": self.employee_name,
            "child_name": self.child_name,
            "telegram_user": self.telegram_user,
            "note": self.note,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "remind_before": self.remind_before,
            "remind_at_time": self.remind_at_time,
            "is_done": self.is_done,
            "repeat_interval_count": self.repeat_interval_count,
            "repeat_interval_unit": self.repeat_interval_unit,
            "occurrence": self.occurrence,
            "user_id": self.user_id,
            "userId": self.user_id,
            "actor_user_id": self.actor_user_id,
        }

    @classmethod
    def from_orm(
        cls,
        event: Any,
        *,
        user_id: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        occurrence: str = "initial",
        event_date_override: Optional[date] = None,
        remind_before_override: Optional[int] = None,
    ) -> "HrEventCreatedEvent":
        remind_before = event.remind_before
        if remind_before_override is not None:
            remind_before = remind_before_override
        return cls(
            hr_event_id=int(event.id),
            type=str(event.type),
            event_date=event_date_override or event.event_date,
            # 0 is valid ("notify on event day"); `or 3` would wrongly turn 0 into 3
            remind_before=(
                3 if remind_before is None else int(remind_before)
            ),
            remind_at_time=_remind_at_time_payload(getattr(event, "remind_at_time", None)),
            employee_name=event.employee_name,
            child_name=event.child_name,
            telegram_user=event.telegram_user,
            note=event.note,
            is_done=bool(event.is_done),
            repeat_interval_count=getattr(event, "repeat_interval_count", None),
            repeat_interval_unit=getattr(event, "repeat_interval_unit", None),
            occurrence=occurrence,
            user_id=user_id,
            actor_user_id=actor_user_id,
        )
