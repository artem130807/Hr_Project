from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class NegotiationBase(BaseModel):
    candidate_id: int = Field(..., example=1)


class NegotiationCreate(NegotiationBase):
    pass


class NegotiationUpdate(NegotiationBase):
    pass



class NegotiationRead(NegotiationBase):
    read: bool = Field(..., example=False)
    created_at: datetime
    updated_at: datetime