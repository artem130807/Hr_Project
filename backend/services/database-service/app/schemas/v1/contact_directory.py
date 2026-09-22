from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

ContactType = Literal["telegram", "phone", "email"]
UsageType = Literal["personal", "work_personal", "shared"]


class ContactPointIn(BaseModel):
    contact_type: ContactType
    value: str = Field(min_length=1, max_length=320)
    usage_type: UsageType
    label: Optional[str] = Field(default=None, max_length=200)
    priority: int = Field(default=100, ge=0, le=10000)
    is_primary: bool = False
    is_active: bool = True
    allow_adaptation: bool = False
    telegram_chat_id: Optional[str] = Field(default=None, max_length=64)
    telegram_username: Optional[str] = Field(default=None, max_length=64)
    verified_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_semantics(self):
        if self.contact_type != "telegram" and (self.telegram_chat_id or self.telegram_username):
            raise ValueError("Telegram fields are allowed only for telegram contacts")
        if self.allow_adaptation and self.contact_type != "telegram":
            raise ValueError("Adaptation delivery can be enabled only for Telegram")
        return self


class ContactPointUpdate(BaseModel):
    value: Optional[str] = Field(default=None, min_length=1, max_length=320)
    usage_type: Optional[UsageType] = None
    label: Optional[str] = Field(default=None, max_length=200)
    priority: Optional[int] = Field(default=None, ge=0, le=10000)
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None
    allow_adaptation: Optional[bool] = None
    telegram_chat_id: Optional[str] = Field(default=None, max_length=64)
    telegram_username: Optional[str] = Field(default=None, max_length=64)
    verified_at: Optional[datetime] = None


class ContactPointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_type: str
    value: str
    normalized_value: str
    usage_type: str
    owner_type: str
    employee_id: Optional[int] = None
    department_id: Optional[int] = None
    label: Optional[str] = None
    priority: int
    is_primary: bool
    is_active: bool
    allow_adaptation: bool
    telegram_chat_id: Optional[str] = None
    telegram_username: Optional[str] = None
    verified_at: Optional[datetime] = None

class DepartmentIn(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    lead_user_id: Optional[str] = Field(default=None, max_length=36)
    lead_name: Optional[str] = Field(default=None, max_length=200)


class RoutingPolicyUpdate(BaseModel):
    allow_personal_telegram_fallback: Optional[bool] = None
    responsible_hr_user_id: Optional[str] = Field(default=None, max_length=36)
    responsible_hr_name: Optional[str] = Field(default=None, max_length=200)
