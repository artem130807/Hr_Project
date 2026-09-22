from pydantic import BaseModel, Field


class AutoSearchCreate(BaseModel):
    vacancy_id: int = Field(..., examples=[1])


class AutoSearchRead(BaseModel):
    id: int = Field(..., examples=[1])
    vacancy_id: int = Field(..., examples=[1])
    total_sent: int = Field(..., examples=[3, 24, 53])
    invite_limit: int = Field(..., examples=[10, 20, 30])
