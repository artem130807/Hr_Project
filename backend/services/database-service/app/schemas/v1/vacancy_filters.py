from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.v1.enums import VacancyFilterAction, WorkExpirience, WorkFormat


def filter_has_criteria(
    *,
    city: Optional[str] = None,
    age_from: Optional[int] = None,
    age_to: Optional[int] = None,
    experience: Optional[WorkExpirience] = None,
    work_format: Optional[WorkFormat] = None,
) -> bool:
    if city and str(city).strip():
        return True
    if age_from is not None or age_to is not None:
        return True
    if experience is not None:
        return True
    if work_format is not None:
        return True
    return False


class VacancyFilterBase(BaseModel):
    city: Optional[str] = Field(None, max_length=200, description="Город")
    age_from: Optional[int] = Field(None, ge=0, le=120, description="Возраст от")
    age_to: Optional[int] = Field(None, ge=0, le=120, description="Возраст до")
    experience: Optional[WorkExpirience] = Field(None, description="Опыт работы")
    work_format: Optional[WorkFormat] = Field(
        None,
        description="Формат работы: remote / office / hybrid / field / shift",
    )
    action: VacancyFilterAction = Field(
        VacancyFilterAction.discard,
        description="discard = отказ неподошедшим; consider = «подумать» подошедшим",
    )

    @model_validator(mode="after")
    def validate_age_range(self):
        if isinstance(self.city, str):
            self.city = self.city.strip() or None
        if (
            self.age_from is not None
            and self.age_to is not None
            and self.age_from > self.age_to
        ):
            raise ValueError("age_from must be <= age_to")
        return self


class VacancyFilterCreate(VacancyFilterBase):
    @model_validator(mode="after")
    def require_at_least_one_criterion(self):
        if not filter_has_criteria(
            city=self.city,
            age_from=self.age_from,
            age_to=self.age_to,
            experience=self.experience,
            work_format=self.work_format,
        ):
            raise ValueError("Укажите хотя бы одно условие фильтра")
        return self


class VacancyFilterUpdate(BaseModel):
    city: Optional[str] = Field(None, max_length=200)
    age_from: Optional[int] = Field(None, ge=0, le=120)
    age_to: Optional[int] = Field(None, ge=0, le=120)
    experience: Optional[WorkExpirience] = None
    work_format: Optional[WorkFormat] = None
    action: Optional[VacancyFilterAction] = None

    @model_validator(mode="after")
    def validate_age_range(self):
        if isinstance(self.city, str):
            self.city = self.city.strip() or None
        if (
            self.age_from is not None
            and self.age_to is not None
            and self.age_from > self.age_to
        ):
            raise ValueError("age_from must be <= age_to")
        return self


class VacancyFilterRead(VacancyFilterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
