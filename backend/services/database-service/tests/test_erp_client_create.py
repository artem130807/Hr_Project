"""Unit tests for ErpClient create/roles (httpx mocked)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.erp.client import ErpClient


@pytest.mark.asyncio
async def test_resolve_role_id_maps_hr_slug():
    client = ErpClient(base_url="https://erp.example.com")
    client.list_roles = AsyncMock(
        return_value=[
            {"id": 7, "name": "HR"},
            {"id": 3, "name": "Менеджер"},
        ]
    )
    assert await client.resolve_role_id("hr", access_token="t") == 7
    assert await client.resolve_role_id("manager", access_token="t") == 3
    assert await client.resolve_role_id("missing", access_token="t") is None


@pytest.mark.asyncio
async def test_create_user_posts_json_and_returns_body():
    client = ErpClient(base_url="https://erp.example.com")
    response = MagicMock()
    response.status_code = 201
    response.json.return_value = {"user": {"id": "u1"}, "password": "Gen1#"}

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=response)

    with patch("app.erp.client.httpx.AsyncClient", return_value=mock_client):
        data = await client.create_user(
            {"name": "N", "email": "a@b.c"},
            access_token="user-jwt",
        )

    assert data["password"] == "Gen1#"
    mock_client.post.assert_awaited_once()
    args, kwargs = mock_client.post.await_args
    assert args[0].endswith("/api/v2/users/")
    assert kwargs["json"]["email"] == "a@b.c"


@pytest.mark.asyncio
async def test_create_user_maps_erp_409():
    client = ErpClient(base_url="https://erp.example.com")
    response = MagicMock()
    response.status_code = 409
    response.json.return_value = {"detail": "Пользователь с таким email уже существует"}
    response.text = "conflict"

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=response)

    with patch("app.erp.client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(HTTPException) as exc:
            await client.create_user({"email": "a@b.c"}, access_token="t")
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_create_user_requires_token():
    client = ErpClient(base_url="https://erp.example.com")
    with patch("app.erp.client.ERP_BEARER_TOKEN", ""):
        with pytest.raises(HTTPException) as exc:
            await client.create_user({"email": "a@b.c"}, access_token="")
    assert exc.value.status_code == 503
