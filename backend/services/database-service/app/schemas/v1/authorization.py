from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

class ServiceCredentials(BaseModel):
    client_id: str
    client_secret: str


class AuthResponse(BaseModel):
    access_token: str = Field(..., example="dskfjh23k4kjh234kjh23ksdf")
    expires: str = Field(..., example="2025-10-12T15:43:21Z")
    token_type: str = Field(default="bearer", example="bearer")
    refresh_token: Optional[str] = Field(
        None,
        description="Opaque refresh token (user sessions only). Store securely.",
    )
    refresh_expires: Optional[str] = Field(
        None,
        description="ISO-8601 expiry of the refresh token",
    )


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=16)


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = Field(
        None,
        description="If provided, revoke this token; otherwise revoke all sessions for the access-token user",
    )


class DecodedToken(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sub: str = Field(..., example="ai-service")
    type: str = Field(default="user", example="service")
    exp: Optional[int] = Field(None, example=1760286722)
    role: Optional[str] = Field(None, example="hr")
    erp_user_id: Optional[str] = Field(None, example="11111111-1111-1111-1111-111111111111")


class TokenVerifyCreate(BaseModel):
    token: str


class MeResponse(BaseModel):
    id: str
    username: str
    full_name: Optional[str] = None
    role: str
    role_id: Optional[int] = None
    department: Optional[str] = None
    erp_user_id: Optional[str] = None
