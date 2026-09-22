from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.t2.auth import ensure_access_token, request_t2_token_refresh
from app.t2.tokens import (
    T2TokenError,
    access_expires_at,
    is_definitive_refresh_failure,
    jwt_exp,
    merge_refreshed_payload,
    should_refresh_access,
)


def _jwt(exp: int) -> str:
    import base64
    import json

    def b64(obj) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{b64({'alg': 'none'})}.{b64({'exp': exp})}.sig"


def test_should_refresh_when_expired_or_unknown():
    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    expired = {"access_token": "a", "refresh_token": "r", "token_expires": "2026-08-25T12:00:00+00:00"}
    fresh = {
        "access_token": "a",
        "refresh_token": "r",
        "token_expires": (now + timedelta(hours=10)).isoformat(),
    }
    assert should_refresh_access(expired, now=now) is True
    assert should_refresh_access(fresh, now=now, skew_seconds=7200) is False
    assert should_refresh_access({"refresh_token": "r", "access_token": "a"}, now=now) is True
    assert should_refresh_access({"access_token": "a"}, now=now) is False
    assert should_refresh_access(fresh, now=now, force=True) is True


def test_jwt_exp_and_merge_uses_access_token_fields():
    exp = int(datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc).timestamp())
    token = _jwt(exp)
    assert jwt_exp(token) == datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
    merged = merge_refreshed_payload(
        {"refresh_token": "old-r", "access_token": "old"},
        {"accessToken": token, "refreshToken": "new-r"},
    )
    assert merged["access_token"] == token
    assert merged["refresh_token"] == "new-r"
    assert access_expires_at(merged) == datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)


def test_merge_falls_back_to_24h_ttl(monkeypatch):
    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    merged = merge_refreshed_payload({}, {"accessToken": "plain-token"}, now=now)
    assert merged["access_token"] == "plain-token"
    assert datetime.fromisoformat(merged["token_expires"]) == now + timedelta(hours=24)


def test_definitive_refresh_failure():
    assert is_definitive_refresh_failure(403, '{"details":"The token is expired"}') is True
    assert is_definitive_refresh_failure(403, '{"details":"The token has already been updated"}') is False
    assert is_definitive_refresh_failure(500, "boom") is False


@pytest.mark.asyncio
async def test_request_refresh_puts_refresh_token_in_authorization():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["Authorization"]
        return httpx.Response(
            200,
            json={"accessToken": "new-a", "refreshToken": "new-r"},
        )

    body = await request_t2_token_refresh(
        "refresh-secret",
        transport=httpx.MockTransport(handler),
    )
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/authorization/refresh/token")
    assert captured["auth"] == "refresh-secret"
    assert body["accessToken"] == "new-a"


@pytest.mark.asyncio
async def test_request_refresh_expired_is_definitive():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"details": "The token is expired"})

    with pytest.raises(T2TokenError) as exc:
        await request_t2_token_refresh("dead", transport=httpx.MockTransport(handler))
    assert exc.value.keep_tokens is False
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_ensure_access_token_refreshes_and_persists():
    stored = {
        "access_token": "old-a",
        "refresh_token": "old-r",
        "token_expires": "2020-01-01T00:00:00+00:00",
    }

    class Repo:
        async def get(self):
            return SimpleNamespace(payload=stored)

        async def upsert(self, payload):
            stored.clear()
            stored.update(payload)
            return SimpleNamespace(payload=payload)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "old-r"
        return httpx.Response(200, json={"accessToken": "new-a", "refreshToken": "new-r"})

    token = await ensure_access_token(Repo(), transport=httpx.MockTransport(handler))
    assert token == "new-a"
    assert stored["refresh_token"] == "new-r"
    assert stored["token_expires"]


@pytest.mark.asyncio
async def test_ensure_access_token_skips_http_when_fresh():
    future = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
    repo = MagicMock()
    repo.get = AsyncMock(
        return_value=SimpleNamespace(
            payload={"access_token": "live", "refresh_token": "r", "token_expires": future}
        )
    )
    repo.upsert = AsyncMock()
    token = await ensure_access_token(repo)
    assert token == "live"
    repo.upsert.assert_not_awaited()
