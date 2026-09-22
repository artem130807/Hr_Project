"""Bearer validation: prefer database-service /token/verify, then JWKS."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.text or str(self.status_code))


@pytest.mark.asyncio
async def test_validate_bearer_accepts_db_verify():
    from app.utils import auth as auth_mod

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_FakeResponse(200, {"sub": "database-service", "type": "service"}))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(auth_mod, "DB_SERVICE_BASE_URL", "http://db:8000/v1"), patch(
        "app.utils.auth.httpx.AsyncClient", return_value=mock_client
    ):
        payload = await auth_mod.validate_bearer_token("svc-jwt")

    assert payload["sub"] == "database-service"
    mock_client.post.assert_awaited()


@pytest.mark.asyncio
async def test_validate_bearer_rejects_when_verify_and_jwks_fail():
    from app.utils import auth as auth_mod

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_FakeResponse(401, text="nope"))
    mock_client.get = AsyncMock(return_value=_FakeResponse(200, {"keys": []}))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(auth_mod, "DB_SERVICE_BASE_URL", "http://db:8000/v1"), patch.object(
        auth_mod, "_public_key", None
    ), patch.object(auth_mod, "JWKS_URL", "http://db:8000/.well-known/jwks.json"), patch(
        "app.utils.auth.httpx.AsyncClient", return_value=mock_client
    ):
        with pytest.raises(HTTPException) as exc:
            await auth_mod.validate_bearer_token("bad")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Could not validate credentials"


def test_token_verify_url_does_not_double_v1():
    from app.utils import auth as auth_mod

    with patch.object(auth_mod, "DB_SERVICE_BASE_URL", "http://db:8000/v1"):
        assert auth_mod._token_verify_url() == "http://db:8000/v1/token/verify"
    with patch.object(auth_mod, "DB_SERVICE_BASE_URL", "http://db:8000"):
        assert auth_mod._token_verify_url() == "http://db:8000/v1/token/verify"


def test_internal_token_ok(monkeypatch):
    from app.utils import auth as auth_mod

    monkeypatch.setenv("INTERNAL_PROXY_SECRET", "s3cret")
    monkeypatch.delenv("HH_SERVICE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("DB_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(auth_mod, "CLIENT_SECRET", None)
    assert auth_mod._internal_token_ok("s3cret") is True
    assert auth_mod._internal_token_ok("other") is False
    assert auth_mod._internal_token_ok(None) is False
