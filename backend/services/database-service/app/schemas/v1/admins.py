from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict
from app.db.v1.enums import AdminRoles, Departments


class AdminUserBase(BaseModel):
    role: str = Field(..., examples=[AdminRoles.hr.value])
    user_id: Optional[int] = Field(None, examples=[2])
    username: str = Field(..., max_length=200, examples=["elena@example.com"])
    full_name: Optional[str] = Field(None, max_length=200, examples=["Елена Иванова"])
    department: Optional[str] = Field(default=None, examples=[Departments.hr.value])
    position: Optional[str] = Field(default=None, examples=["Менеджер"])
    negotations_processing: Optional[bool] = Field(None)
    erp_user_id: Optional[str] = Field(None, max_length=36, examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    date_hired: Optional[date] = Field(default=None, description="Дата выхода сотрудника на работу")


class AdminUserCreate(AdminUserBase):
    """Create panel user in ERP. Password optional — ERP generates one if omitted."""

    plain_password: Optional[str] = Field(None, max_length=72, examples=["abcdefght"])


class AdminUserRead(AdminUserBase):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdminUserCreateResponse(BaseModel):
    user: AdminUserRead
    password: Optional[str] = Field(
        None,
        description="Generated password when plain_password was omitted",
    )


class ErpRoleRead(BaseModel):
    id: int
    name: Optional[str] = None
    role: Optional[str] = Field(
        None,
        description="Mapped HR panel role slug (hr, manager, …)",
    )


class AdminUserUpdate(BaseModel):
    role: Optional[str] = Field(default=None, examples=[AdminRoles.lead.value])
    user_id: Optional[int] = Field(default=None, examples=[2])
    username: Optional[str] = Field(default=None, max_length=200)
    full_name: Optional[str] = Field(default=None, max_length=200)
    plain_password: Optional[str] = Field(default=None, max_length=72)
    department: Optional[str] = Field(default=None)
    negotations_processing: Optional[bool] = None
    erp_user_id: Optional[str] = Field(default=None, max_length=36)
    date_hired: Optional[date] = None


class ErpUserSyncItem(BaseModel):
    erp_user_id: str
    username: str
    full_name: Optional[str] = None
    role: str
    department: Optional[str] = None


class ErpUserSyncRequest(BaseModel):
    users: list[ErpUserSyncItem] = Field(default_factory=list)


class ErpUserSyncResult(BaseModel):
    created: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class ResponsibleForNegotiations(BaseModel):
    responsible_of_negotiations: bool = True
