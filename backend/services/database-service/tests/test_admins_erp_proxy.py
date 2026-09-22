"""Admins directory proxies ERP users (no local panel table)."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.endpoints.v1 import admins as mod
from app.schemas.v1.admins import AdminUserCreate


def _request(auth: str | None = "Bearer erp-token") -> Request:
    headers = []
    if auth:
        headers.append((b"authorization", auth.encode()))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/admin/user",
        "headers": headers,
        "query_string": b"",
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_list_erp_admins_maps_roles_and_flags():
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        MagicMock(erp_user_id="u-1", negotations_processing=True),
    ]
    db.execute = AsyncMock(return_value=result)

    with patch.object(mod, "ERP_BASE", "https://erp.example.com"), patch.object(
        mod.ErpClient,
        "list_users",
        new=AsyncMock(
            return_value=[
                {
                    "id": "u-1",
                    "email": "m@ex.com",
                    "name": "Manager",
                    "is_active": True,
                    "role": {"name": "Менеджер"},
                },
                {
                    "id": "u-2",
                    "email": "x@ex.com",
                    "name": "Off",
                    "is_active": False,
                    "role": {"name": "HR"},
                },
            ]
        ),
    ):
        items = await mod._list_erp_admins(db)

    assert len(items) == 1
    assert items[0]["id"] == "u-1"
    assert items[0]["role"] == "manager"
    assert items[0]["negotations_processing"] is True


def test_erp_user_mapper_keeps_work_start_date():
    from app.erp.mapper import map_erp_user

    mapped = map_erp_user({
        "id": "u-1",
        "email": "m@ex.com",
        "name": "Manager",
        "is_active": True,
        "role": {"name": "Менеджер"},
        "date_hired": "2026-09-21",
    })

    assert mapped["date_hired"] == "2026-09-21"


@pytest.mark.asyncio
async def test_create_admin_proxies_to_erp():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )
    body = AdminUserCreate(
        role="hr",
        username="new@ex.com",
        full_name="Новый HR",
        plain_password="Secret1#",
        date_hired=date(2026, 9, 21),
    )
    client = MagicMock()
    client.resolve_role_id = AsyncMock(return_value=7)
    client.create_user = AsyncMock(
        return_value={
            "user": {
                "id": "new-id",
                "email": "new@ex.com",
                "name": "Новый HR",
                "is_active": True,
                "date_hired": "2026-09-21",
                "role": {"id": 7, "name": "HR"},
            },
            "password": None,
        }
    )

    with patch.object(mod, "ERP_BASE", "https://erp.example.com"), patch.object(
        mod, "ErpClient", return_value=client
    ):
        result = await mod.post_admin_user_endpoint(body, _request(), db, token="erp-token")

    assert result["user"]["id"] == "new-id"
    assert result["user"]["role"] == "hr"
    assert result["password"] is None
    client.create_user.assert_awaited_once()
    payload = client.create_user.await_args.args[0]
    assert payload["email"] == "new@ex.com"
    assert payload["role_id"] == 7
    assert payload["password"] == "Secret1#"
    assert payload["date_hired"] == "2026-09-21"
    # Endpoint returns the raw mapped payload; FastAPI's response model serializes
    # and validates it as a date at the HTTP boundary.
    assert result["user"]["date_hired"] == "2026-09-21"


@pytest.mark.asyncio
async def test_create_admin_rejects_non_email_login():
    body = AdminUserCreate(role="hr", username="ivanov", full_name="Ivan", plain_password="x")
    with patch.object(mod, "ERP_BASE", "https://erp.example.com"):
        with pytest.raises(HTTPException) as exc:
            await mod.post_admin_user_endpoint(body, _request(), MagicMock(), token="t")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_admin_returns_generated_password_when_omitted():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )
    body = AdminUserCreate(role="manager", username="m@ex.com", full_name="Mgr", plain_password=None)
    client = MagicMock()
    client.resolve_role_id = AsyncMock(return_value=3)
    client.create_user = AsyncMock(
        return_value={
            "user": {
                "id": "mgr-1",
                "email": "m@ex.com",
                "name": "Mgr",
                "is_active": True,
                "role": {"id": 3, "name": "Менеджер"},
            },
            "password": "Generated1#",
        }
    )
    with patch.object(mod, "ERP_BASE", "https://erp.example.com"), patch.object(
        mod, "ErpClient", return_value=client
    ):
        result = await mod.post_admin_user_endpoint(body, _request(), db, token="erp-token")
    assert result["password"] == "Generated1#"
    assert "password" not in client.create_user.await_args.args[0]


@pytest.mark.asyncio
async def test_create_admin_unknown_role_returns_400():
    body = AdminUserCreate(role="hr", username="h@ex.com", full_name="H", plain_password="Secret1#")
    client = MagicMock()
    client.resolve_role_id = AsyncMock(return_value=None)
    with patch.object(mod, "ERP_BASE", "https://erp.example.com"), patch.object(
        mod, "ErpClient", return_value=client
    ):
        with pytest.raises(HTTPException) as exc:
            await mod.post_admin_user_endpoint(body, _request(), MagicMock(), token="t")
    assert exc.value.status_code == 400
    assert "Роль" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_list_admin_roles_maps_erp_roles():
    client = MagicMock()
    client.list_roles = AsyncMock(
        return_value=[
            {"id": 7, "name": "HR", "permissions": []},
            {"id": 3, "name": "Менеджер", "permissions": []},
        ]
    )
    with patch.object(mod, "ERP_BASE", "https://erp.example.com"), patch.object(
        mod, "ErpClient", return_value=client
    ):
        roles = await mod.list_admin_roles_endpoint(_request(), token="erp-token")
    assert {r["role"] for r in roles} >= {"hr", "manager"}


@pytest.mark.asyncio
async def test_update_admin_proxies_to_erp():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )
    from app.schemas.v1.admins import AdminUserUpdate

    body = AdminUserUpdate(
        role="manager",
        full_name="Новое Имя",
        username="m@ex.com",
        date_hired=date(2026, 9, 21),
    )
    client = MagicMock()
    client.resolve_role_id = AsyncMock(return_value=3)
    client.update_user = AsyncMock(
        return_value={
            "id": "u-1",
            "email": "m@ex.com",
            "name": "Новое Имя",
            "is_active": True,
            "role": {"id": 3, "name": "Менеджер"},
        }
    )
    with patch.object(mod, "ERP_BASE", "https://erp.example.com"), patch.object(
        mod, "ErpClient", return_value=client
    ):
        result = await mod.update_admin_user_endpoint(
            "u-1", body, _request(), db, token="erp-token"
        )

    assert result["id"] == "u-1"
    assert result["role"] == "manager"
    assert result["full_name"] == "Новое Имя"
    client.update_user.assert_awaited_once()
    payload = client.update_user.await_args.args[1]
    assert payload["email"] == "m@ex.com"
    assert payload["role_id"] == 3
    assert payload["name"] == "Новое Имя"
    assert payload["date_hired"] == "2026-09-21"


@pytest.mark.asyncio
async def test_reset_password_proxies_to_erp():
    client = MagicMock()
    client.reset_user_password = AsyncMock(return_value={"status": "ok", "password": "NewPass1#"})
    with patch.object(mod, "ERP_BASE", "https://erp.example.com"), patch.object(
        mod, "ErpClient", return_value=client
    ):
        result = await mod.reset_admin_user_password_endpoint(
            "u-1", _request(), token="erp-token"
        )
    assert result["password"] == "NewPass1#"
