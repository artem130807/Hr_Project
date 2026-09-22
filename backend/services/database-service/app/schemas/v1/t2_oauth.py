from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class T2OAuthTokenPayload(BaseModel):
    access_token: Optional[str] = Field(None, examples=["T2_ACCESS"])
    refresh_token: Optional[str] = Field(None, examples=["T2_REFRESH"])
    token_expires: Optional[str] = Field(None, examples=["2026-08-20T12:00:00+00:00"])


class T2OAuthTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payload: Optional[T2OAuthTokenPayload] = None
    updated_at: Optional[datetime] = None
    version: Optional[int] = Field(None, examples=[1])


class OkResponse(BaseModel):
    ok: bool = True
