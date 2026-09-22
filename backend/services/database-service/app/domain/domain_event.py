"""Базовый контракт доменных / интеграционных событий."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID


class DomainEvent(ABC):
    """Конкретные события — frozen dataclass с ``event_id`` / ``occurred_at``."""

    event_type: ClassVar[str]

    @abstractmethod
    def payload(self) -> dict[str, Any]:
        """Бизнес-поля события без метаданных."""

    def to_dict(self) -> dict[str, Any]:
        event_id = getattr(self, "event_id", None)
        occurred_at = getattr(self, "occurred_at", None)
        if isinstance(occurred_at, datetime):
            occurred_at = occurred_at.isoformat()
        if isinstance(event_id, UUID):
            event_id = str(event_id)
        return {
            "event_id": event_id,
            "event_type": self.event_type,
            "occurred_at": occurred_at,
            **self.payload(),
        }
