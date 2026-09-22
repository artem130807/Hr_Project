"""Schemas for standalone public professional (Q&A) test results."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class PublicTestResultSubmit(BaseModel):
    test_id: int = Field(..., gt=0)
    candidate_id: Optional[int] = Field(default=None, gt=0)
    result_id: Optional[int] = Field(default=None, gt=0)
    full_name: Optional[str] = Field(default=None, max_length=200)
    position: Optional[str] = Field(default=None, max_length=200)
    taken_at: Optional[date] = None
    answers: dict[str, Any] = Field(
        ...,
        description="question_id → string | {value, option_index, violations, forced_incorrect}",
    )
    timed_out: bool = False
    integrity: Optional[dict[str, Any]] = Field(
        default=None,
        description="Aggregate integrity stats: tab_blur_count, mouse_leave_count, duration_seconds",
    )

    @field_validator("full_name", "position")
    @classmethod
    def strip_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        return v or None

    @model_validator(mode="after")
    def require_identity_unless_linked(self):
        linked = self.candidate_id is not None or self.result_id is not None
        if not linked and (not self.full_name or not self.position or self.taken_at is None):
            raise ValueError("ФИО, должность и дата обязательны")
        return self

    @field_validator("answers", mode="before")
    @classmethod
    def coerce_answers(cls, v: Any) -> dict[str, Any]:
        if not isinstance(v, dict) or not v:
            raise ValueError("Нужны ответы")
        out: dict[str, Any] = {}
        for key, value in v.items():
            if value is None:
                continue
            if isinstance(value, dict):
                out[str(key)] = value
                continue
            text = str(value).strip()
            if not text:
                continue
            out[str(key)] = text
        if not out:
            raise ValueError("Нужны ответы")
        return out


class PublicTestResultRead(BaseModel):
    id: int
    test_id: int
    test_name: Optional[str] = None
    full_name: str
    position: str
    taken_at: date
    answers: dict[str, Any]
    score: Optional[int] = None
    max_score: Optional[int] = None
    timed_out: bool = False
    integrity: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PublicTestResultListItem(BaseModel):
    id: int
    test_id: int
    test_name: Optional[str] = None
    full_name: str
    position: str
    taken_at: date
    score: Optional[int] = None
    max_score: Optional[int] = None
    timed_out: bool = False
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
