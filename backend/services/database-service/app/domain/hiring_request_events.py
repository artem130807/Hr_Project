"""Доменное событие: создана заявка на подбор.

Готовый ``text`` и список ролей передаются через ``message.entity_changed``;
message-service создаёт отдельные role-уведомления без общего канала.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Optional
from uuid import UUID, uuid4

from app.domain.domain_event import DomainEvent


@dataclass(frozen=True)
class HiringRequestCreatedEvent(DomainEvent):
    """Событие: в HR создана заявка на подбор → уведомления целевым ролям."""

    event_type: ClassVar[str] = "message.hiring_request.created"

    hiring_request_id: int
    text: str
    target_role_ids: tuple[int, ...]
    actor_user_id: Optional[str] = None
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def payload(self) -> dict[str, Any]:
        return {
            "hiring_request_id": self.hiring_request_id,
            "text": self.text,
            "target_role_ids": list(self.target_role_ids),
            "actor_user_id": self.actor_user_id,
        }
