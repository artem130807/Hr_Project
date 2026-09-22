from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VnrHireRead(BaseModel):
    id: int
    hr_user_id: str
    hr_user_name: Optional[str] = None
    candidate_id: int
    employee_id: Optional[int] = None
    vacancy_id: Optional[int] = None
    full_name: str
    department: Optional[str] = None
    position: Optional[str] = None
    hired_at: datetime
    left_at: Optional[datetime] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HrProfileStats(BaseModel):
    hr_user_id: str
    hired: int = Field(0, description="Все трудоустроенные (ВНР) этим HR")
    in_work: int = Field(0, description="Из них всё ещё в работе (не уволились)")
    interviews: int = Field(0, description="Забронированные собеседования в HR-календаре")
    interviews_this_week: int = Field(0, description="Собеседования на текущей неделе (пн–вс)")
