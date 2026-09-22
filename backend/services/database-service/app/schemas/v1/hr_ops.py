from datetime import date, datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, Field

from app.db.v1.enums import Gender, MaritalStatus


class EmployeeCreate(BaseModel):
    user_id: Optional[int] = None
    erp_user_id: Optional[str] = Field(default=None, max_length=36)
    candidate_id: Optional[int] = None
    full_name: str
    department: str
    position: str
    gender: Optional[Gender] = None
    phone_number: Optional[str] = None
    marital_status: Optional[MaritalStatus] = None
    hobbies: Optional[List[str]] = None
    personal_characteristics: Optional[str] = None
    birth_date: Optional[date] = None
    age: Optional[int] = None
    service_length: Optional[int] = 0
    date_hired: Optional[date] = None
    date_fired: Optional[date] = None
    adaptation_route: Optional[Literal["full", "control"]] = None


class EmployeeUpdate(BaseModel):
    erp_user_id: Optional[str] = Field(default=None, max_length=36)
    full_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    gender: Optional[Gender] = None
    phone_number: Optional[str] = None
    marital_status: Optional[MaritalStatus] = None
    hobbies: Optional[List[str]] = None
    personal_characteristics: Optional[str] = None
    birth_date: Optional[date] = None
    age: Optional[int] = None
    service_length: Optional[int] = None
    date_hired: Optional[date] = None
    date_fired: Optional[date] = None


class EmployeeRead(BaseModel):
    id: int
    user_id: Optional[int] = None
    erp_user_id: Optional[str] = None
    candidate_id: Optional[int] = None
    full_name: str
    department: str
    position: str
    gender: Optional[Gender] = None
    phone_number: Optional[str] = None
    marital_status: Optional[MaritalStatus] = None
    hobbies: Optional[List[str]] = None
    personal_characteristics: Optional[str] = None
    birth_date: Optional[date] = None
    age: Optional[int] = None
    service_length: Optional[int] = None
    date_hired: date
    date_fired: Optional[date] = None
    archived_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApprovalCreate(BaseModel):
    vacancy_id: int
    candidate_id: int
    approver_id: str
    approver_name: Optional[str] = None
    new_status: str
    comments: str = ""


class ApprovalRead(BaseModel):
    id: int
    vacancy_id: int
    candidate_id: int
    approver_id: str
    approver_name: Optional[str] = None
    new_status: str
    comments: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CandidateCommentCreate(BaseModel):
    body: str = Field(..., min_length=1)
    author_id: Optional[str] = None
    author_name: Optional[str] = None


class CandidateCommentRead(BaseModel):
    id: int
    candidate_id: int
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    body: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StageHistoryRead(BaseModel):
    id: int
    candidate_id: int
    from_stage: Optional[str] = None
    to_stage: Optional[str] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogRead(BaseModel):
    id: int
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    details: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class HireResult(BaseModel):
    candidate_id: int
    employee_id: int
    stage: str
    message: str = "Candidate hired and employee record created"
