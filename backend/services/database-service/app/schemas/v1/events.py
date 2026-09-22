from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.events.recurrence import PERMANENT_TYPE, REPEAT_UNITS, normalize_repeat


def _parse_optional_time(value: object) -> Optional[time]:
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(raw, fmt).time()
            except ValueError:
                continue
        raise ValueError("remind_at_time must be HH:MM or HH:MM:SS")
    raise ValueError("remind_at_time must be a time or HH:MM string")


class EventBase(BaseModel):
    type: str = Field(
        ...,
        examples=["birthday", "child_birthday", "work_anniversary", "interview", "other", "permanent"],
    )
    employee_name: Optional[str] = Field(None, examples=["Иван Иванов"])
    child_name: Optional[str] = Field(None, examples=["Мария"])
    telegram_user: Optional[str] = Field(None, examples=["@ivan_hr"])
    note: Optional[str] = Field(None, examples=["Поздравить в общем чате"])
    event_date: date
    remind_before: int = Field(3, ge=0)
    remind_at_time: Optional[time] = Field(None, examples=["10:30:00"])
    is_done: bool = False
    repeat_interval_count: Optional[int] = Field(None, ge=1, le=365, examples=[1])
    repeat_interval_unit: Optional[str] = Field(None, examples=["month"])

    @field_validator("remind_at_time", mode="before")
    @classmethod
    def validate_remind_at_time(cls, value: object) -> Optional[time]:
        return _parse_optional_time(value)

    @field_validator("repeat_interval_unit", mode="before")
    @classmethod
    def normalize_unit(cls, value: object) -> Optional[str]:
        if value is None or value == "":
            return None
        return str(value).strip().lower()

    @model_validator(mode="after")
    def validate_repeat_policy(self):
        if str(self.type or "").strip().lower() == PERMANENT_TYPE:
            if not self.repeat_interval_unit:
                raise ValueError("Для постоянного события укажите интервал повтора")
            count, unit = normalize_repeat(self.repeat_interval_count, self.repeat_interval_unit)
            self.repeat_interval_count = count
            self.repeat_interval_unit = unit
        else:
            self.repeat_interval_count = None
            self.repeat_interval_unit = None
        return self


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    type: Optional[str] = None
    employee_name: Optional[str] = None
    child_name: Optional[str] = None
    telegram_user: Optional[str] = None
    note: Optional[str] = None
    event_date: Optional[date] = None
    remind_before: Optional[int] = Field(None, ge=0)
    remind_at_time: Optional[time] = None
    is_done: Optional[bool] = None
    repeat_interval_count: Optional[int] = Field(None, ge=1, le=365)
    repeat_interval_unit: Optional[str] = None

    @field_validator("remind_at_time", mode="before")
    @classmethod
    def validate_remind_at_time(cls, value: object) -> Optional[time]:
        return _parse_optional_time(value)

    @field_validator("repeat_interval_unit", mode="before")
    @classmethod
    def normalize_unit(cls, value: object) -> Optional[str]:
        if value is None or value == "":
            return None
        unit = str(value).strip().lower()
        if unit not in REPEAT_UNITS:
            raise ValueError("Некорректный интервал постоянного события")
        return unit


class EventRead(EventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    last_dispatched_at: Optional[datetime] = None
    next_dispatch_at: Optional[datetime] = None


class ErpEmployeeSuggestion(BaseModel):
    erp_user_id: str = Field(..., examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    full_name: Optional[str] = Field(None, examples=["Иван Иванов"])
    username: Optional[str] = Field(None, examples=["ivan@example.com"])
    tg_username: Optional[str] = Field(None, examples=["@ivan_hr"])
