"""TDD: HR user auth proxies to erp-backend (no local user table)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from app.erp.auth_bridge import (
    erp_pair_to_auth_response,
    normalize_erp_access_payload,
    me_from_erp,
)
from app.erp.mapper import map_role


class TestNormalizeErpPayload:
    def test_flattens_nested_role_and_sets_user_type(self):
        payload = {
            "sub": "hr@example.com",
            "user_id": "uuid-1",
            "role": {"name": "Менеджер", "permissions": ["x"]},
            "exp": 1,
        }
        out = normalize_erp_access_payload(payload)
        assert out["type"] == "user"
        assert out["role"] == "manager"
        assert out["sub"] == "hr@example.com"
        assert out["erp_user_id"] == "uuid-1"


class TestErpPairToAuthResponse:
    def test_maps_expires_in_to_iso_expires(self):
        before = datetime.now(timezone.utc)
        resp = erp_pair_to_auth_response(
            {
                "access_token": "access",
                "refresh_token": "refresh-token-value-long",
                "token_type": "bearer",
                "expires_in": 1800,
            }
        )
        assert resp["access_token"] == "access"
        assert resp["refresh_token"] == "refresh-token-value-long"
        expires = datetime.fromisoformat(resp["expires"].replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        delta = (expires - before).total_seconds()
        assert 1790 <= delta <= 1815


def test_me_from_erp_uses_uuid_as_id():
    me = me_from_erp(
        access_payload={"sub": "a@b.c", "user_id": "erp-uuid", "role": {"name": "hr"}},
        erp_me={"id": "erp-uuid", "email": "a@b.c", "name": "Ann", "role": {"name": "HR"}},
    )
    assert me["id"] == "erp-uuid"
    assert me["erp_user_id"] == "erp-uuid"
    assert me["role"] == "hr"
    assert me["full_name"] == "Ann"


def test_me_from_erp_exposes_numeric_role_id():
    from_profile = me_from_erp(
        access_payload={"sub": "a@b.c", "user_id": "erp-uuid", "role_id": 2},
        erp_me={
            "id": "erp-uuid",
            "email": "a@b.c",
            "role": {"id": 7, "name": "HR"},
        },
    )
    assert from_profile["role_id"] == 7

    from_jwt = me_from_erp(
        access_payload={"sub": "a@b.c", "user_id": "erp-uuid", "role_id": 4, "role": {"name": "Руководитель"}},
        erp_me=None,
    )
    assert from_jwt["role_id"] == 4
    assert from_jwt["role"] == "leader"


@pytest.mark.asyncio
async def test_login_proxies_to_erp():
    from app.endpoints.v1 import authorization as mod

    form = SimpleNamespace(username="u@example.com", password="secret")
    request = MagicMock()
    request.headers = {"user-agent": "pytest"}
    request.client = SimpleNamespace(host="127.0.0.1")

    erp_pair = {
        "access_token": "erp-access",
        "refresh_token": "erp-refresh-token-xxxxxxxxxxxx",
        "token_type": "bearer",
        "expires_in": 900,
    }

    with patch.object(mod, "ERP_AUTH_ENABLED", True), patch.object(
        mod, "ERP_JWT_SECRET", "test-secret"
    ), patch.object(mod, "erp_login", AsyncMock(return_value=erp_pair)) as login_mock:
        resp = await mod.get_access_token_for_user_endpoint(request, form)

    login_mock.assert_awaited_once()
    assert resp["access_token"] == "erp-access"
    assert resp["refresh_token"] == "erp-refresh-token-xxxxxxxxxxxx"


@pytest.mark.asyncio
async def test_login_requires_erp_secret():
    from app.endpoints.v1 import authorization as mod

    form = SimpleNamespace(username="u", password="p")
    request = MagicMock()
    request.headers = {}
    request.client = None

    with patch.object(mod, "ERP_AUTH_ENABLED", True), patch.object(mod, "ERP_JWT_SECRET", ""):
        with pytest.raises(HTTPException) as exc:
            await mod.get_access_token_for_user_endpoint(request, form)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_refresh_proxies_to_erp():
    from app.endpoints.v1 import authorization as mod
    from app.schemas.v1.authorization import RefreshTokenRequest

    body = RefreshTokenRequest(refresh_token="erp-refresh-token-xxxxxxxxxxxx")

    with patch.object(mod, "ERP_AUTH_ENABLED", True), patch.object(
        mod, "ERP_JWT_SECRET", "x"
    ), patch.object(
        mod,
        "erp_refresh",
        AsyncMock(
            return_value={
                "access_token": "new-access",
                "refresh_token": "new-refresh-token-xxxxxxxxxxxx",
                "token_type": "bearer",
                "expires_in": 900,
            }
        ),
    ):
        resp = await mod.refresh_access_token_endpoint(body)

    assert resp["access_token"] == "new-access"


@pytest.mark.asyncio
async def test_get_current_user_accepts_erp_hs256_token():
    from app.utils import utils as utils_mod

    secret = "test-erp-secret"
    token = jwt.encode(
        {
            "sub": "erp@example.com",
            "user_id": "abc",
            "role": {"name": "lead", "permissions": []},
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        secret,
        algorithm="HS256",
    )
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    with patch.object(utils_mod, "ERP_AUTH_ENABLED", True), patch.object(
        utils_mod, "ERP_JWT_SECRET", secret
    ), patch.object(utils_mod, "ERP_JWT_ALGORITHM", "HS256"):
        payload = await utils_mod.get_current_user(token)

    assert payload["sub"] == "erp@example.com"
    assert payload["type"] == "user"
    assert payload["role"] == "lead"


def test_map_role_keeps_erp_aligned_values():
    assert map_role({"name": "superadmin"}) == "superadmin"
    assert map_role({"name": "Руководитель отдела"}) == "dept_leader"


def test_web_admin_panel_user_model_removed():
    from app.db import v1 as models_pkg
    import app.db.v1.models as models

    assert not hasattr(models, "WebAdminPanelUser")
    assert not hasattr(models, "RefreshToken")
