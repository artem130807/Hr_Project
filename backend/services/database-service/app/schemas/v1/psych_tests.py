"""Schemas for standalone psychological test results."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class PsychResultSubmit(BaseModel):
    instrument_id: str = Field(..., min_length=1, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=200)
    position: str = Field(..., min_length=1, max_length=200)
    taken_at: date
    birth_date: date
    answers: dict[str, Any] = Field(
        ...,
        description="Код вопроса → шкала 1..5 | парный выбор {most,least} | выбор рабочей ситуации A-D",
    )
    timing: Optional[dict[str, Any]] = None

    @field_validator("full_name", "position")
    @classmethod
    def strip_required(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Поле обязательно")
        return v

    @field_validator("answers", mode="before")
    @classmethod
    def coerce_answers(cls, v: Any) -> dict[str, Any]:
        if not isinstance(v, dict) or not v:
            raise ValueError("Нужны ответы")
        out: dict[str, Any] = {}
        for key, value in v.items():
            if value is None or value == "":
                continue
            if isinstance(value, dict):
                most = str(value.get("most") or value.get("answer_primary") or "").strip().upper()
                least = str(value.get("least") or value.get("answer_secondary") or "").strip().upper()
                if most or least:
                    out[str(key)] = {"most": most or None, "least": least or None}
                elif value.get("choice"):
                    out[str(key)] = str(value.get("choice")).strip().upper()
                continue
            if isinstance(value, str) and value.strip().upper() in {"A", "B", "C", "D"}:
                out[str(key)] = value.strip().upper()
                continue
            try:
                raw = int(value)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Некорректный ответ: {key}") from e
            if 1 <= raw <= 5:
                out[str(key)] = raw
                continue
            raise ValueError(f"Ответ вне диапазона: {key}")
        if not out:
            raise ValueError("Нужны ответы")
        return out

    @model_validator(mode="after")
    def birth_date_must_be_plausible(self):
        if self.birth_date > date.today():
            raise ValueError("Дата рождения не может быть в будущем")
        if self.birth_date > self.taken_at:
            raise ValueError("Дата рождения не может быть позже даты прохождения")
        return self


class PsychResultRead(BaseModel):
    id: int
    instrument_id: str
    instrument_version: Optional[str] = None
    full_name: str
    position: str
    taken_at: date
    birth_date: Optional[date] = None
    chs: Optional[int] = None
    chm: Optional[int] = None
    answers: dict[str, Any]
    scores: dict[str, Any]
    quality_status: Optional[str] = None
    behavior_preference: Optional[str] = Field(default=None, validation_alias="leading_disc")
    management_focus: Optional[str] = Field(default=None, validation_alias="leading_paei")
    work_style_focus: Optional[str] = Field(default=None, validation_alias="leading_work10")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PsychResultListItem(BaseModel):
    id: int
    instrument_id: str
    instrument_version: Optional[str] = None
    full_name: str
    position: str
    taken_at: date
    birth_date: Optional[date] = None
    chs: Optional[int] = None
    chm: Optional[int] = None
    quality_status: Optional[str] = None
    behavior_preference: Optional[str] = Field(default=None, validation_alias="leading_disc")
    management_focus: Optional[str] = Field(default=None, validation_alias="leading_paei")
    work_style_focus: Optional[str] = Field(default=None, validation_alias="leading_work10")
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
