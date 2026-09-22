"""T2 OAuth token store: model, repository, HTTP adapters."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.v1.models import T2OAuthToken
from app.endpoints.v1.t2_oauth import (
    delete_t2_oauth_tokens,
    get_t2_oauth_tokens,
    put_t2_oauth_tokens,
)
from app.repositories.t2_oauth_token_repository import T2OAuthTokenRepository
from app.schemas.v1.t2_oauth import T2OAuthTokenPayload, T2OAuthTokenResponse, OkResponse


def test_t2_oauth_payload_schema():
    body = T2OAuthTokenPayload(
        access_token="a",
        refresh_token="r",
        token_expires="2026-08-20T12:00:00+00:00",
    )
    dumped = body.model_dump()
    assert dumped["access_token"] == "a"
    assert dumped["refresh_token"] == "r"


def test_t2_oauth_routes_registered():
    from app.endpoints.v1.t2_oauth import router

    paths = {getattr(r, "path", None) for r in router.routes}
    assert "/t2-oauth/tokens" in paths
    methods = {
        method
        for r in router.routes
        if getattr(r, "path", None) == "/t2-oauth/tokens"
        for method in (getattr(r, "methods", None) or set())
    }
    assert {"GET", "PUT", "DELETE"} <= methods


def test_t2_oauth_token_model_mirrors_hh_columns():
    from app.db.v1.models import HhOAuthToken

    assert T2OAuthToken.__tablename__ == "t2_oauth_tokens"
    assert set(T2OAuthToken.__table__.c.keys()) == set(HhOAuthToken.__table__.c.keys())
    assert T2OAuthToken.INITIAL_VERSION == 1


@pytest.mark.asyncio
async def test_repository_get_empty():
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    repo = T2OAuthTokenRepository(db)
    assert await repo.get() is None
    db.get.assert_awaited_once_with(T2OAuthToken, 1)


@pytest.mark.asyncio
async def test_repository_upsert_inserts_then_bumps():
    stored = {}

    async def _get(_cls, pk):
        return stored.get(pk)

    db = MagicMock()
    db.get = AsyncMock(side_effect=_get)
    db.add = MagicMock(side_effect=lambda row: stored.__setitem__(row.id, row))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    repo = T2OAuthTokenRepository(db)
    created = await repo.upsert(
        {"access_token": "acc", "refresh_token": "ref", "token_expires": "t"}
    )
    assert created.version == T2OAuthToken.INITIAL_VERSION
    assert stored[1].payload["access_token"] == "acc"

    updated = await repo.upsert({"access_token": "acc2", "refresh_token": "ref2"})
    assert updated.version == 2
    assert stored[1].payload["access_token"] == "acc2"


@pytest.mark.asyncio
async def test_repository_delete_missing_and_existing():
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    repo = T2OAuthTokenRepository(db)
    assert await repo.delete() is False
    db.delete.assert_not_called()

    row = T2OAuthToken(id=1, payload={"access_token": "x"}, version=1)
    db.get = AsyncMock(return_value=row)
    assert await repo.delete() is True
    db.delete.assert_awaited_once_with(row)
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_get_tokens_empty():
    repo = MagicMock()
    repo.get = AsyncMock(return_value=None)
    result = await get_t2_oauth_tokens(repo)
    assert isinstance(result, T2OAuthTokenResponse)
    assert result.payload is None
    assert result.version is None


@pytest.mark.asyncio
async def test_put_tokens_via_repository():
    row = T2OAuthToken(
        id=1,
        payload={"access_token": "acc", "refresh_token": "ref"},
        version=1,
    )
    row.updated_at = datetime(2026, 8, 19, 12, 0, 0)
    repo = MagicMock()
    repo.upsert = AsyncMock(return_value=row)
    body = T2OAuthTokenPayload(access_token="acc", refresh_token="ref")
    result = await put_t2_oauth_tokens(body, repo)
    repo.upsert.assert_awaited_once_with(body.model_dump())
    assert result.payload.access_token == "acc"
    assert result.version == 1


@pytest.mark.asyncio
async def test_delete_tokens_endpoint():
    repo = MagicMock()
    repo.delete = AsyncMock(return_value=True)
    result = await delete_t2_oauth_tokens(repo)
    assert isinstance(result, OkResponse)
    assert result.ok is True
    repo.delete.assert_awaited_once()
