from pydantic import BaseModel, Field


class AuthResponse(BaseModel):
    access_token: str = Field(..., example="dskfjh23k4kjh234kjh23ksdf")
    expires: str = Field(..., example="2025-10-12T15:43:21Z")
    token_type: str = Field(..., example="bearer")