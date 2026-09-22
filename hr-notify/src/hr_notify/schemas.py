"""HR notify schemas (message-service → hr.event.notify)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


class HrEventNotify(BaseModel):
    event_id: str = ""
    event_type: str = "hr.event.notify"
    occurred_at: Optional[str] = None
    hr_event_id: int = 0
    type: str = ""
    employee_name: Optional[str] = None
    child_name: Optional[str] = None
    telegram_user: Optional[str] = None
    note: Optional[str] = None
    event_date: str = ""
    remind_before: int = 0
    remind_at_time: Optional[str] = None
    notify_at: str
    hiring_request_id: int = 0
    actor_name: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    headcount: Optional[int] = None
    user_id: str = ""
    content: str

    @field_validator("content")
    @classmethod
    def content_required(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("content is required")
        return text

    @classmethod
    def from_json_bytes(cls, body: bytes) -> "HrEventNotify":
        return cls.model_validate_json(body)

    def notify_at_dt(self) -> datetime:
        raw = (self.notify_at or "").strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)


def parse_hr_event_notify(data: dict[str, Any] | bytes | str) -> HrEventNotify:
    if isinstance(data, (bytes, bytearray)):
        return HrEventNotify.from_json_bytes(bytes(data))
    if isinstance(data, str):
        return HrEventNotify.model_validate_json(data)
    return HrEventNotify.model_validate(data)
