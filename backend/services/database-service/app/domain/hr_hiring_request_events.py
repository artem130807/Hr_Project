"""Доменное событие: создана заявка на подбор (поток как hr.event.created).

Публикуется в ``message.entity_changed``. message-service кладёт outbox
``hr.event.notify`` с notify_at=сейчас → opened-monitor-bot шлёт Telegram сразу.
Канал «Заявки на подбор» живёт отдельным событием ``message.hiring_request.created``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Optional
from uuid import UUID, uuid4

from app.domain.domain_event import DomainEvent


def _str(value: Any) -> Optional[str]:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    text = str(raw).strip()
    return text or None


def _int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n


def actor_display_name(req: Any, actor_name: Optional[str] = None) -> Optional[str]:
    """ФИО создавшего заявку: заголовок актора, иначе инициатор/руководитель."""
    return (
        _str(actor_name)
        or _str(getattr(req, "initiator_name", None))
        or _str(getattr(req, "manager_name", None))
    )


@dataclass(frozen=True)
class HrHiringRequestCreatedEvent(DomainEvent):
    """Создана заявка на подбор → Telegram через message-service / бот."""

    event_type: ClassVar[str] = "hr.hiring_request.created"

    hiring_request_id: int
    text: str
    position: Optional[str] = None
    department: Optional[str] = None
    headcount: Optional[int] = None
    urgency: Optional[str] = None
    initiator_name: Optional[str] = None
    manager_name: Optional[str] = None
    actor_user_id: Optional[str] = None
    actor_name: Optional[str] = None
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def payload(self) -> dict[str, Any]:
        data = {
            "hiring_request_id": self.hiring_request_id,
            "position": self.position,
            "department": self.department,
            "headcount": self.headcount,
            "urgency": self.urgency,
            "initiator_name": self.initiator_name,
            "manager_name": self.manager_name,
            "actor_user_id": self.actor_user_id,
            "actor_name": self.actor_name,
            "text": self.text,
        }
        return {key: value for key, value in data.items() if value is not None}

    @classmethod
    def from_orm(
        cls,
        req: Any,
        *,
        text: str,
        actor_user_id: Optional[str] = None,
        actor_name: Optional[str] = None,
    ) -> "HrHiringRequestCreatedEvent":
        resolved_actor = actor_display_name(req, actor_name)
        return cls(
            hiring_request_id=int(getattr(req, "id", 0) or 0),
            text=text,
            position=_str(getattr(req, "position", None)),
            department=_str(getattr(req, "department", None)),
            headcount=_int(getattr(req, "headcount", None)),
            urgency=_str(getattr(req, "urgency", None)),
            initiator_name=_str(getattr(req, "initiator_name", None)),
            manager_name=_str(getattr(req, "manager_name", None)),
            actor_user_id=_str(actor_user_id),
            actor_name=resolved_actor,
        )
