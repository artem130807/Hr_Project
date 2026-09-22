from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any


class BaseContact(BaseModel):
    hr_id: Optional[str] = Field(None, description="ERP UUID HR менеджера, ответственного за контакт")
    name: str = Field(..., description="Имя контактного лица")
    email: Optional[str] = Field(None, description="Email для связи")
    phone_number: List[str] = Field(..., description="Список номеров телефонов")


class CreateContact(BaseContact):
    pass


class ReadContact(BaseContact):
    id: int = Field(..., description="Уникальный идентификатор контакта")
    created_at: datetime = Field(..., description="Дата и время создания контакта")
    updated_at: datetime = Field(..., description="Дата и время последнего обновления контакта")

    class Config:
        from_attributes = True

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _coerce_dt(cls, v: Any):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


class UpdateContact(BaseModel):
    name: Optional[str] = Field(None, description="Имя контактного лица")
    email: Optional[str] = Field(None, description="Email для связи")
    phone_number: Optional[List[str]] = Field(None, description="Список номеров телефонов")
