"""HH auth link/status proxied through database-service."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_proxy_hh_auth_link_builds_locally_when_configured():
    from app.endpoints.v1 import vacancies as mod

    with patch.object(mod.conf, "HH_CLIENT_ID", "cid"), patch.object(
        mod.conf, "HH_REDIRECT_URI", "https://example/callback"
    ), patch.object(mod, "_proxy_hh_import", new=AsyncMock()) as proxy:
        resp = await mod.proxy_hh_auth_link()

    assert resp.media_type.startswith("text/plain")
    body = resp.body.decode()
    assert body.startswith("https://hh.ru/oauth/authorize?")
    assert "client_id=cid" in body
    assert "redirect_uri=" in body
    proxy.assert_not_awaited()


@pytest.mark.asyncio
async def test_proxy_hh_auth_link_falls_back_to_hh_service():
    from app.endpoints.v1 import vacancies as mod

    with patch.object(mod.conf, "HH_CLIENT_ID", None), patch.object(
        mod.conf, "HH_REDIRECT_URI", None
    ), patch.object(
        mod,
        "_proxy_hh_import",
        new=AsyncMock(return_value="https://hh.ru/oauth/authorize?client_id=1"),
    ):
        resp = await mod.proxy_hh_auth_link()

    assert resp.body.decode() == "https://hh.ru/oauth/authorize?client_id=1"


@pytest.mark.asyncio
async def test_proxy_hh_auth_link_rejects_garbage():
    from app.endpoints.v1 import vacancies as mod

    with patch.object(mod.conf, "HH_CLIENT_ID", None), patch.object(
        mod.conf, "HH_REDIRECT_URI", None
    ), patch.object(mod, "_proxy_hh_import", new=AsyncMock(return_value={"oops": True})):
        with pytest.raises(HTTPException) as exc:
            await mod.proxy_hh_auth_link()
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_proxy_hh_auth_passed():
    from app.endpoints.v1 import vacancies as mod

    with patch.object(
        mod,
        "_proxy_hh_import",
        new=AsyncMock(return_value={"auth_passed": False}),
    ) as proxy:
        result = await mod.proxy_hh_auth_passed()
    assert result == {"auth_passed": False}
    proxy.assert_awaited_once_with("GET", "auth-passed", timeout=15.0)
