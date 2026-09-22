from typing import Optional, Union
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.v1.enums import (
    BotRoles
)


class BaseBotUser(BaseModel):
    telegram_id: str = Field(..., example='1685316319')
    name: str = Field(..., example='istendlay')
    role: BotRoles = Field(..., example=BotRoles.candidate.value)

    class Config:
        use_enum_values = True


class BotUserCreate(BaseBotUser):
    candidate_id: Optional[int] = Field(default=None)
    employee_id: Optional[int] = Field(default=None)
    admin_id: Optional[str] = Field(default=None)


class BotUserRead(BaseBotUser):
    id: int = Field(..., example='1')
    # candidate_id: Optional[int] = Field(example=4)
    # employee_id: Optional[int] = Field(example=7)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BotUserDelete(BaseModel):
    id: int = Field(..., example='1')


class BotUserUpdate(BaseModel):
    telegram_id: Optional[str] = Field(None, example='1685316319')
    name: Optional[str] = Field(None, example='istendlay')
    role: Optional[BotRoles] = Field(None, example=BotRoles.candidate.value)
    candidate_profile_id: Optional[int] = Field(None, example=1)
    employee_profile_id: Optional[int] = Field(None, example=1)

    class Config:
        use_enum_values = True


class InviteTokenCreate(BaseModel):
    role: BotRoles = Field(..., example=BotRoles.candidate.value)
    id: Union[int, str] = Field(..., example=1)


class InviteTokenRead(BaseModel):
    id: int = Field(..., example=1)

    token: str = Field(..., example="9cv3NMHkwuna6piQqAqiaQ")
    role: BotRoles = Field(..., example=BotRoles.candidate.value)
    entity_id: str = Field(..., description='candidate ID or ERP user UUID')

    expires_at: datetime = Field(..., example='')



class BaseProgress(BaseModel):
    vacancy_description: Optional[bool] = Field(default=False, example=True)
    company_info: Optional[bool] = Field(default=False, example=True)
    corp_culture: Optional[bool] = Field(default=False, example=False)
    my_resume: Optional[bool] = Field(default=False, example=True)
    agreement: Optional[bool] = Field(None, example=False)
    test_disc: Optional[bool] = Field(None, example=False)
    test_adizes: Optional[bool] = Field(None, example=False)


class UpdateProgress(BaseModel):
    vacancy_description: Optional[bool] = Field(None, example=False)
    company_info: Optional[bool] = Field(None, example=False)
    corp_culture: Optional[bool] = Field(None, example=False)
    my_resume: Optional[bool] = Field(None, example=False)
    agreement: Optional[bool] = Field(None, example=False)
    test_disc: Optional[bool] = Field(None, example=False)
    test_adizes: Optional[bool] = Field(None, example=False)


class ReadProgress(BaseProgress):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True