"""HH OAuth token store (PG singleton) schemas + endpoint behaviour."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.v1.models import HhOAuthToken
from app.endpoints.v1.hh_oauth import (
    delete_hh_oauth_tokens,
    get_hh_oauth_tokens,
    put_hh_oauth_tokens,
)
from app.schemas.v1.hh_oauth import HhOAuthTokenPayload, HhOAuthTokenResponse, OkResponse


def test_hh_oauth_payload_schema():
    body = HhOAuthTokenPayload(
        access_token="a",
        refresh_token="r",
        token_expires="2026-08-20T12:00:00+00:00",
    )
    dumped = body.model_dump()
    assert dumped["access_token"] == "a"
    assert dumped["refresh_token"] == "r"


def test_hh_oauth_routes_registered():
    from main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/v1/hh-oauth/tokens" in paths
    assert "/v1/hh-oauth/login-url" in paths
    assert "/v1/hh-oauth/status" in paths


def test_hh_oauth_token_model_is_singleton():
    assert HhOAuthToken.__tablename__ == "hh_oauth_tokens"
    pk = HhOAuthToken.__table__.c.id
    assert pk.primary_key
    assert pk.autoincrement is False or pk.autoincrement == "auto"
    assert "version" in HhOAuthToken.__table__.c
    assert HhOAuthToken.INITIAL_VERSION == 1


@pytest.mark.asyncio
async def test_get_tokens_empty():
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    result = await get_hh_oauth_tokens(db)
    assert isinstance(result, HhOAuthTokenResponse)
    assert result.payload is None
    assert result.updated_at is None
    assert result.version is None
    db.get.assert_awaited_once_with(HhOAuthToken, 1)


@pytest.mark.asyncio
async def test_put_tokens_inserts_then_get():
    stored = {}

    async def _get(_cls, pk):
        return stored.get(pk)

    db = MagicMock()
    db.get = AsyncMock(side_effect=_get)
    db.add = MagicMock(side_effect=lambda row: stored.__setitem__(row.id, row))
    db.commit = AsyncMock()

    async def _refresh(row):
        row.updated_at = datetime(2026, 8, 19, 12, 0, 0)

    db.refresh = AsyncMock(side_effect=_refresh)

    body = HhOAuthTokenPayload(access_token="acc", refresh_token="ref", token_expires="t")
    created = await put_hh_oauth_tokens(body, db)
    assert created.payload.access_token == "acc"
    assert created.version == HhOAuthToken.INITIAL_VERSION
    assert 1 in stored
    assert stored[1].payload["refresh_token"] == "ref"
    assert stored[1].version == HhOAuthToken.INITIAL_VERSION
    db.add.assert_called_once()

    got = await get_hh_oauth_tokens(db)
    assert got.payload.access_token == "acc"
    assert got.version == HhOAuthToken.INITIAL_VERSION


@pytest.mark.asyncio
async def test_put_tokens_upserts_existing():
    row = HhOAuthToken(id=1, payload={"access_token": "old"}, version=1)
    db = MagicMock()
    db.get = AsyncMock(return_value=row)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    body = HhOAuthTokenPayload(access_token="new", refresh_token="r2")
    result = await put_hh_oauth_tokens(body, db)
    assert row.payload["access_token"] == "new"
    assert result.payload.access_token == "new"
    assert row.version == 2
    assert result.version == 2
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_put_tokens_marks_json_modified():
    from unittest.mock import patch as _patch

    row = HhOAuthToken(id=1, payload={"access_token": "old"})
    db = MagicMock()
    db.get = AsyncMock(return_value=row)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    with _patch("app.endpoints.v1.hh_oauth.flag_modified") as flagged:
        await put_hh_oauth_tokens(HhOAuthTokenPayload(access_token="new"), db)
    flagged.assert_called_once_with(row, "payload")


@pytest.mark.asyncio
async def test_delete_tokens():
    row = HhOAuthToken(id=1, payload={"access_token": "x"})
    db = MagicMock()
    db.get = AsyncMock(return_value=row)
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    result = await delete_hh_oauth_tokens(db)
    assert isinstance(result, OkResponse)
    assert result.ok is True
    db.delete.assert_awaited_once_with(row)


@pytest.mark.asyncio
async def test_delete_tokens_noop_when_missing():
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    db.delete = AsyncMock()
    result = await delete_hh_oauth_tokens(db)
    assert result.ok is True
    db.delete.assert_not_called()
