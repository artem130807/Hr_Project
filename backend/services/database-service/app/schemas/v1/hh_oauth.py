from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class HhOAuthTokenPayload(BaseModel):
    """Same JSON shape as Redis key ``hh_oauth_tokens``."""

    access_token: Optional[str] = Field(None, examples=["HH_ACCESS"])
    refresh_token: Optional[str] = Field(None, examples=["HH_REFRESH"])
    token_expires: Optional[str] = Field(None, examples=["2026-08-20T12:00:00+00:00"])


class HhOAuthTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payload: Optional[HhOAuthTokenPayload] = None
    updated_at: Optional[datetime] = None
    version: Optional[int] = Field(
        None,
        description="Aggregate revision of the singleton row; None when no tokens stored",
        examples=[1],
    )


class OkResponse(BaseModel):
    ok: bool = True
