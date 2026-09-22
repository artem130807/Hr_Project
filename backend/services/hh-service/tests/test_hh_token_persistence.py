"""HH OAuth token persistence: dual-write, smart clear, PG restore, keepalive."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.clients.hh.simple_hh_client import HHTokenManager, SimpleHHClient
from app.scheduler import scheduler as sched_mod


def _manager(*, access="acc", refresh="ref", expires_in=3600, redis=None, db=None):
    return HHTokenManager(
        "cid",
        "secret",
        access_token=access,
        refresh_token=refresh,
        expires_in=expires_in,
        redis_client=redis,
        db_client=db,
    )


def test_is_definitive_oauth_failure():
    cls = HHTokenManager
    assert cls.is_definitive_oauth_failure(400, "token not found")
    assert cls.is_definitive_oauth_failure(400, "{}", "invalid_grant")
    assert cls.is_definitive_oauth_failure(401, "", "invalid_client")
    assert not cls.is_definitive_oauth_failure(500, "token not found")
    assert not cls.is_definitive_oauth_failure(400, "gateway timeout", "server_error")
    assert not cls.is_definitive_oauth_failure(503, "unavailable")


def test_is_placeholder_token():
    assert HHTokenManager.is_placeholder_token("fake-hh-access-token")
    assert HHTokenManager.is_placeholder_token("fake-hh-refresh-token")
    assert not HHTokenManager.is_placeholder_token("real-token")
    assert not HHTokenManager.is_placeholder_token("")
    assert not HHTokenManager.is_placeholder_token(None)


@pytest.mark.asyncio
async def test_save_tokens_dual_write():
    redis = AsyncMock()
    db = AsyncMock()
    db.put = AsyncMock(return_value={"payload": {"access_token": "acc"}, "updated_at": None})
    tm = _manager(redis=redis, db=db)
    await tm._save_tokens()
    redis.set.assert_awaited_once()
    key, raw = redis.set.await_args.args
    assert key == HHTokenManager.REDIS_KEY
    payload = json.loads(raw)
    assert payload["access_token"] == "acc"
    assert payload["refresh_token"] == "ref"
    db.put.assert_awaited_once_with(HHTokenManager.DB_TOKENS_PATH, json=payload)


@pytest.mark.asyncio
async def test_save_tokens_skips_placeholder_values():
    redis = AsyncMock()
    db = AsyncMock()
    tm = _manager(access="fake-hh-access-token", refresh="fake-hh-refresh-token", redis=redis, db=db)
    await tm._save_tokens()
    redis.set.assert_not_called()
    db.put.assert_not_called()


@pytest.mark.asyncio
async def test_save_tokens_pg_empty_response_keeps_redis():
    redis = AsyncMock()
    db = AsyncMock()
    db.put = AsyncMock(return_value=None)
    tm = _manager(redis=redis, db=db)
    await tm._save_tokens()
    redis.set.assert_awaited_once()
    db.put.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_tokens_pg_failure_does_not_raise():
    redis = AsyncMock()
    db = AsyncMock()
    db.put = AsyncMock(side_effect=RuntimeError("pg down"))
    tm = _manager(redis=redis, db=db)
    await tm._save_tokens()
    redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_clear_tokens_wipes_memory_redis_and_pg():
    redis = AsyncMock()
    db = AsyncMock()
    tm = _manager(redis=redis, db=db)
    await tm._clear_tokens()
    assert tm.access_token is None
    assert tm.refresh_token is None
    redis.delete.assert_awaited_once_with(HHTokenManager.REDIS_KEY)
    db.delete.assert_awaited_once_with(HHTokenManager.DB_TOKENS_PATH)


@pytest.mark.asyncio
async def test_load_from_db_reads_payload():
    db = AsyncMock()
    db.get = AsyncMock(
        return_value={
            "payload": {"access_token": "from-pg", "refresh_token": "r"},
            "updated_at": "2026-08-19T00:00:00",
        }
    )
    data = await HHTokenManager.load_from_db(db)
    assert data["access_token"] == "from-pg"
    db.get.assert_awaited_once_with(HHTokenManager.DB_TOKENS_PATH)


@pytest.mark.asyncio
async def test_load_from_db_empty_without_access_token():
    db = AsyncMock()
    db.get = AsyncMock(return_value={"payload": {"refresh_token": "only-r"}})
    assert await HHTokenManager.load_from_db(db) == {}
    db.get = AsyncMock(return_value=None)
    assert await HHTokenManager.load_from_db(db) == {}
    assert await HHTokenManager.load_from_db(None) == {}


@pytest.mark.asyncio
async def test_get_token_returns_live_access_without_refresh():
    tm = _manager(expires_in=3600)
    tm._refresh_tokens = AsyncMock()
    assert await tm.get_token() == "acc"
    tm._refresh_tokens.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_token_without_refresh_is_http_502():
    from fastapi import HTTPException

    tm = _manager(access=None, refresh=None, expires_in=0)
    with pytest.raises(HTTPException) as exc:
        await tm.get_token()
    assert exc.value.status_code == 502
    assert "Войти в HH" in str(exc.value.detail)


def _patch_httpx_post(resp_or_exc):
    instance = AsyncMock()
    if isinstance(resp_or_exc, Exception):
        instance.post = AsyncMock(side_effect=resp_or_exc)
    else:
        instance.post = AsyncMock(return_value=resp_or_exc)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=instance)
    cm.__aexit__ = AsyncMock(return_value=None)
    return patch("app.clients.hh.simple_hh_client.httpx.AsyncClient", return_value=cm)


@pytest.mark.asyncio
async def test_refresh_network_error_keeps_tokens():
    redis = AsyncMock()
    db = AsyncMock()
    tm = _manager(access=None, redis=redis, db=db)
    with _patch_httpx_post(httpx.RequestError("timeout")):
        with pytest.raises(RuntimeError, match="сеть"):
            await tm._refresh_tokens()
    assert tm.refresh_token == "ref"
    redis.delete.assert_not_called()
    db.delete.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_transient_5xx_keeps_tokens():
    redis = AsyncMock()
    db = AsyncMock()
    tm = _manager(access=None, redis=redis, db=db)
    resp = MagicMock()
    resp.status_code = 503
    resp.text = "unavailable"
    resp.json.return_value = {"error": "server_error"}
    with _patch_httpx_post(resp):
        with pytest.raises(RuntimeError, match="transient"):
            await tm._refresh_tokens()
    assert tm.refresh_token == "ref"
    redis.delete.assert_not_called()
    db.delete.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_definitive_invalid_grant_clears_tokens():
    redis = AsyncMock()
    db = AsyncMock()
    tm = _manager(access=None, redis=redis, db=db)
    resp = MagicMock()
    resp.status_code = 400
    resp.text = '{"error":"invalid_grant","error_description":"token not found"}'
    resp.json.return_value = {"error": "invalid_grant", "error_description": "token not found"}
    with _patch_httpx_post(resp):
        with pytest.raises(RuntimeError, match="Не удалось обновить токен HH"):
            await tm._refresh_tokens()
    assert tm.access_token is None
    assert tm.refresh_token is None
    redis.delete.assert_awaited_once()
    db.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_success_saves_rotated_tokens():
    redis = AsyncMock()
    db = AsyncMock()
    tm = _manager(access=None, redis=redis, db=db)
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "access_token": "new-acc",
        "refresh_token": "new-ref",
        "expires_in": 86400,
    }
    with _patch_httpx_post(resp):
        token = await tm._refresh_tokens()
    assert token == "new-acc"
    assert tm.refresh_token == "new-ref"
    redis.set.assert_awaited_once()
    db.put.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_hh_client_restores_from_postgres_when_redis_empty():
    import app.dependencies as deps

    deps._hh_client = None
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    db = AsyncMock()
    db.get = AsyncMock(
        return_value={
            "payload": {
                "access_token": "pg-acc",
                "refresh_token": "pg-ref",
                "token_expires": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
            }
        }
    )

    with patch.object(deps, "get_redis_client", new=AsyncMock(return_value=redis)), patch.object(
        deps, "get_db_client", new=AsyncMock(return_value=db)
    ), patch.object(deps.conf, "HH_ACCESS_TOKEN", ""), patch.object(
        deps.conf, "HH_REFRESH_TOKEN", ""
    ), patch.object(deps.conf, "HH_FORCE_ENV_TOKENS", False):
        client = await deps.get_hh_client()

    try:
        assert client.token_manager.access_token == "pg-acc"
        assert client.token_manager.refresh_token == "pg-ref"
        assert client.token_manager._db is db
        redis.set.assert_awaited_once()
        raw = redis.set.await_args.args[1]
        assert json.loads(raw)["access_token"] == "pg-acc"
    finally:
        deps._hh_client = None


@pytest.mark.asyncio
async def test_get_hh_client_prefers_redis_over_env():
    import app.dependencies as deps

    deps._hh_client = None
    redis = AsyncMock()
    redis.get = AsyncMock(
        return_value=json.dumps(
            {
                "access_token": "redis-acc",
                "refresh_token": "redis-ref",
                "token_expires": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            }
        )
    )
    db = AsyncMock()

    with patch.object(deps, "get_redis_client", new=AsyncMock(return_value=redis)), patch.object(
        deps, "get_db_client", new=AsyncMock(return_value=db)
    ), patch.object(deps.conf, "HH_ACCESS_TOKEN", "fake-hh-access-token"), patch.object(
        deps.conf, "HH_REFRESH_TOKEN", "fake-hh-refresh-token"
    ), patch.object(deps.conf, "HH_FORCE_ENV_TOKENS", False):
        client = await deps.get_hh_client()

    try:
        assert client.token_manager.access_token == "redis-acc"
        db.get.assert_not_called()
    finally:
        deps._hh_client = None


@pytest.mark.asyncio
async def test_get_hh_client_ignores_placeholder_env_when_stores_empty():
    import app.dependencies as deps

    deps._hh_client = None
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    db = AsyncMock()
    db.get = AsyncMock(return_value={"payload": None, "updated_at": None})

    with patch.object(deps, "get_redis_client", new=AsyncMock(return_value=redis)), patch.object(
        deps, "get_db_client", new=AsyncMock(return_value=db)
    ), patch.object(deps.conf, "HH_ACCESS_TOKEN", "fake-hh-access-token"), patch.object(
        deps.conf, "HH_REFRESH_TOKEN", "fake-hh-refresh-token"
    ), patch.object(deps.conf, "HH_FORCE_ENV_TOKENS", True):
        client = await deps.get_hh_client()

    try:
        assert client.token_manager.access_token is None
        assert client.token_manager.refresh_token is None
        redis.set.assert_not_called()
        db.put.assert_not_called()
    finally:
        deps._hh_client = None


@pytest.mark.asyncio
async def test_simple_hh_client_passes_db_client():
    db = AsyncMock()
    client = SimpleHHClient("cid", "sec", db_client=db)
    assert client.token_manager._db is db


@pytest.mark.asyncio
async def test_keepalive_skips_when_token_fresh():
    lock = MagicMock()
    lock.__aenter__ = AsyncMock(return_value=True)
    lock.__aexit__ = AsyncMock(return_value=None)
    hh = MagicMock()
    hh.token_manager.refresh_token = "r"
    hh.token_manager.token_expires = datetime.now(timezone.utc) + timedelta(hours=10)
    hh.token_manager._refresh_tokens = AsyncMock()

    with patch.object(sched_mod, "DistributedLock", return_value=lock), patch(
        "app.dependencies.get_hh_client", new=AsyncMock(return_value=hh)
    ):
        await sched_mod.safe_token_keepalive()

    hh.token_manager._refresh_tokens.assert_not_awaited()


@pytest.mark.asyncio
async def test_keepalive_refreshes_when_expiry_near():
    lock = MagicMock()
    lock.__aenter__ = AsyncMock(return_value=True)
    lock.__aexit__ = AsyncMock(return_value=None)
    hh = MagicMock()
    hh.token_manager.refresh_token = "r"
    hh.token_manager.token_expires = datetime.now(timezone.utc) + timedelta(minutes=30)
    hh.token_manager._refresh_tokens = AsyncMock()

    with patch.object(sched_mod, "DistributedLock", return_value=lock), patch(
        "app.dependencies.get_hh_client", new=AsyncMock(return_value=hh)
    ):
        await sched_mod.safe_token_keepalive()

    hh.token_manager._refresh_tokens.assert_awaited_once()


@pytest.mark.asyncio
async def test_keepalive_warns_without_refresh_token():
    lock = MagicMock()
    lock.__aenter__ = AsyncMock(return_value=True)
    lock.__aexit__ = AsyncMock(return_value=None)
    hh = MagicMock()
    hh.token_manager.refresh_token = None
    hh.token_manager._refresh_tokens = AsyncMock()

    with patch.object(sched_mod, "DistributedLock", return_value=lock), patch(
        "app.dependencies.get_hh_client", new=AsyncMock(return_value=hh)
    ):
        await sched_mod.safe_token_keepalive()

    hh.token_manager._refresh_tokens.assert_not_awaited()
