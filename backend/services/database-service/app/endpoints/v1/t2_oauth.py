"""Durable T2 PBX OAuth token store (singleton row id=1). No T2 API calls."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.middleware import get_db
from app.repositories.t2_oauth_token_repository import T2OAuthTokenRepository
from app.schemas.v1.t2_oauth import T2OAuthTokenPayload, T2OAuthTokenResponse, OkResponse

router = APIRouter()


def get_t2_oauth_token_repository(
    db: AsyncSession = Depends(get_db),
) -> T2OAuthTokenRepository:
    return T2OAuthTokenRepository(db)


def _to_response(row) -> T2OAuthTokenResponse:
    if row is None:
        return T2OAuthTokenResponse(payload=None, updated_at=None, version=None)
    payload = row.payload if isinstance(row.payload, dict) else None
    return T2OAuthTokenResponse(
        payload=payload,
        updated_at=getattr(row, "updated_at", None),
        version=row.version,
    )


@router.get("/t2-oauth/tokens", response_model=T2OAuthTokenResponse)
async def get_t2_oauth_tokens(
    repo: T2OAuthTokenRepository = Depends(get_t2_oauth_token_repository),
) -> T2OAuthTokenResponse:
    return _to_response(await repo.get())


@router.put("/t2-oauth/tokens", response_model=T2OAuthTokenResponse)
async def put_t2_oauth_tokens(
    body: T2OAuthTokenPayload,
    repo: T2OAuthTokenRepository = Depends(get_t2_oauth_token_repository),
) -> T2OAuthTokenResponse:
    return _to_response(await repo.upsert(body.model_dump()))


@router.delete("/t2-oauth/tokens", response_model=OkResponse)
async def delete_t2_oauth_tokens(
    repo: T2OAuthTokenRepository = Depends(get_t2_oauth_token_repository),
) -> OkResponse:
    await repo.delete()
    return OkResponse(ok=True)
