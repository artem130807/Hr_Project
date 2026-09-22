"""Durable HH.ru OAuth token store (singleton row id=1)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db.middleware import get_db
from app.db.v1.models import HhOAuthToken
from app.schemas.v1.hh_oauth import HhOAuthTokenPayload, HhOAuthTokenResponse, OkResponse

router = APIRouter()

_SINGLETON_ID = 1


@router.get("/hh-oauth/tokens", response_model=HhOAuthTokenResponse)
async def get_hh_oauth_tokens(db: AsyncSession = Depends(get_db)) -> HhOAuthTokenResponse:
    row = await db.get(HhOAuthToken, _SINGLETON_ID)
    if row is None:
        return HhOAuthTokenResponse(payload=None, updated_at=None, version=None)
    payload = row.payload if isinstance(row.payload, dict) else None
    return HhOAuthTokenResponse(
        payload=payload,
        updated_at=row.updated_at,
        version=row.version,
    )


@router.put("/hh-oauth/tokens", response_model=HhOAuthTokenResponse)
async def put_hh_oauth_tokens(
    body: HhOAuthTokenPayload,
    db: AsyncSession = Depends(get_db),
) -> HhOAuthTokenResponse:
    payload = body.model_dump()
    row = await db.get(HhOAuthToken, _SINGLETON_ID)
    if row is None:
        row = HhOAuthToken(
            id=_SINGLETON_ID,
            payload=payload,
            version=HhOAuthToken.INITIAL_VERSION,
        )
        db.add(row)
    else:
        row.payload = payload
        flag_modified(row, "payload")
        row.bump_version()
    await db.commit()
    await db.refresh(row)
    return HhOAuthTokenResponse(
        payload=row.payload,
        updated_at=row.updated_at,
        version=row.version,
    )


@router.delete("/hh-oauth/tokens", response_model=OkResponse)
async def delete_hh_oauth_tokens(db: AsyncSession = Depends(get_db)) -> OkResponse:
    row = await db.get(HhOAuthToken, _SINGLETON_ID)
    if row is not None:
        await db.delete(row)
        await db.commit()
    return OkResponse(ok=True)


@router.get("/hh-oauth/login-url")
async def hh_oauth_login_url():
    """Authorize URL. Lives next to /hh-oauth/tokens — prod edge 404s /hh/connect/*."""
    from app.endpoints.v1.vacancies import proxy_hh_auth_link

    return await proxy_hh_auth_link()


@router.get("/hh-oauth/status")
async def hh_oauth_status():
    """Whether HH tokens exist (via hh-service). Same namespace as /hh-oauth/tokens."""
    from app.endpoints.v1.vacancies import proxy_hh_auth_passed

    return await proxy_hh_auth_passed()
