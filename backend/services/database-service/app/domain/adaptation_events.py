"""Доменное событие запроса сотрудника на конфиденциальный разговор с HR."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar
from uuid import UUID, uuid4

from app.domain.domain_event import DomainEvent


@dataclass(frozen=True)
class AdaptationTalkHRRequestedEvent(DomainEvent):
    event_type: ClassVar[str] = "message.adaptation.talk_hr"

    checkpoint_id: int
    text: str
    target_role_ids: tuple[int, ...]
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def payload(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "text": self.text,
            "target_role_ids": list(self.target_role_ids),
        }


@dataclass(frozen=True)
class AdaptationNotificationEvent(DomainEvent):
    """Scheduled role notification; delivery time is controlled by the HR worker."""

    event_type: ClassVar[str] = "message.adaptation.notification"

    checkpoint_id: int
    notification_type: str
    text: str
    target_role_ids: tuple[int, ...]
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def payload(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "notification_type": self.notification_type,
            "text": self.text,
            "target_role_ids": list(self.target_role_ids),
        }
