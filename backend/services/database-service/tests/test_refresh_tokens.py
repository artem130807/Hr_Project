"""Refresh helpers remain; local refresh persistence removed (ERP owns sessions)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.utils.refresh_tokens import (
    generate_refresh_token,
    hash_refresh_token,
    is_refresh_token_active,
    REFRESH_TOKEN_BYTES,
)


class TestRefreshTokenHelpers:
    def test_generate_refresh_token_is_opaque_and_unique(self):
        a = generate_refresh_token()
        b = generate_refresh_token()
        assert isinstance(a, str)
        assert len(a) >= 43
        assert a != b
        assert "." not in a

    def test_hash_refresh_token_is_sha256_hex(self):
        raw = "test-refresh-token-value"
        digest = hash_refresh_token(raw)
        assert digest == hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert len(digest) == 64

    def test_is_active_when_not_revoked_and_not_expired(self):
        token = SimpleNamespace(
            revoked_at=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        assert is_refresh_token_active(token) is True

    def test_is_inactive_when_revoked(self):
        token = SimpleNamespace(
            revoked_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        assert is_refresh_token_active(token) is False

    def test_refresh_token_bytes_constant_is_secure(self):
        assert REFRESH_TOKEN_BYTES >= 32


class TestLocalRefreshRemoved:
    @pytest.mark.asyncio
    async def test_issue_raises(self):
        from app.utils.refresh_tokens import issue_refresh_token

        with pytest.raises(RuntimeError):
            await issue_refresh_token(None, user_id=1)


class TestAuthSchemas:
    def test_refresh_request_schema(self):
        from app.schemas.v1.authorization import RefreshTokenRequest

        req = RefreshTokenRequest(refresh_token="abc123456789012345")
        assert req.refresh_token == "abc123456789012345"


class TestAuthRoutesRegistered:
    def test_refresh_and_logout_routes_exist(self):
        from app.endpoints.v1.authorization import router

        paths = {route.path for route in router.routes}
        assert "/token/user" in paths
        assert "/token/refresh" in paths
        assert "/token/logout" in paths
        assert "/token/service" in paths
        assert "/me" in paths


class TestCreateTokenExpClaim:
    def test_access_token_exp_is_unix_timestamp(self):
        import jwt
        from app.utils.utils import create_token, _public_key
        from app.config import ALGORITHM

        token, expires = create_token(
            data={"sub": "tester", "type": "service"},
            expires_delta=30,
        )
        payload = jwt.decode(token, _public_key, algorithms=[ALGORITHM])
        assert isinstance(payload["exp"], int)
        assert abs(payload["exp"] - int(expires.timestamp())) <= 1
