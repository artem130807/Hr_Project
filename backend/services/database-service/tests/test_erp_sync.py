"""ERP role mapping + sync pull/create flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.v1.enums import AdminRoles
from app.erp.mapper import (
    ALLOWED_ROLES,
    DEFAULT_ERP_ROLE_ALIASES,
    derive_username,
    map_erp_user,
    map_erp_users,
    map_role,
)
from app.erp.client import ErpClient
from app.erp.sync import apply_erp_user_batch, sync_users_from_erp, _as_role


def test_admin_roles_include_erp_and_hr():
    values = {r.value for r in AdminRoles}
    assert "hr" in values
    for expected in (
        "owner",
        "lead",
        "art",
        "dev",
        "superadmin",
        "admin",
        "manager",
        "leader",
        "dept_leader",
        "senior_manager",
    ):
        assert expected in values
    assert ALLOWED_ROLES == values


@pytest.mark.parametrize(
    "erp_name,expected",
    [
        ("Менеджер", "manager"),
        ("Админ", "admin"),
        ("Руководитель", "leader"),
        ("Руководитель отдела", "dept_leader"),
        ("Старший менеджер", "senior_manager"),
        ("superadmin", "superadmin"),
        ("HR", "hr"),
        ("hr", "hr"),
        ("Кадры", "hr"),
        ("кадровик", "hr"),
        ("Lead", "lead"),
        ("Owner", "owner"),
        ("Dev", "dev"),
        ("Разработчик", "dev"),
    ],
)
def test_map_role_erp_names(erp_name, expected):
    assert map_role({"id": 1, "name": erp_name}) == expected


def test_map_role_unknown_falls_back_to_default():
    assert map_role({"name": "Гость"}) in ALLOWED_ROLES


def test_derive_username_from_email():
    assert derive_username("ivanov@example.com", "abc") == "ivanov@example.com"


def test_derive_username_fallback():
    assert derive_username(None, "a1b2c3d4-e5f6-7890-abcd-ef1234567890").startswith("erp_")


def test_map_erp_user_manager_role():
    raw = {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "name": "Иванов Иван",
        "email": "ivanov@example.com",
        "ati_token": None,
        "is_active": True,
        "role": {"id": 3, "name": "Менеджер", "permission": {}, "permissions": ["trips.read"]},
        "phone": "+79001234567",
    }
    mapped = map_erp_user(raw)
    assert mapped == {
        "erp_user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "username": "ivanov@example.com",
        "full_name": "Иванов Иван",
        "role": "manager",
        "department": "Менеджер",
        "position": "Менеджер",
    }
    assert "phone" not in mapped


def test_map_erp_user_leader_and_admin():
    leader = map_erp_user(
        {
            "id": "1",
            "is_active": True,
            "email": "lead@ex.com",
            "name": "Leader",
            "role": {"id": 4, "name": "Руководитель"},
        }
    )
    admin = map_erp_user(
        {
            "id": "2",
            "is_active": True,
            "email": "admin@ex.com",
            "name": "Admin",
            "role": {"id": 2, "name": "Админ"},
        }
    )
    assert leader["role"] == "leader"
    assert admin["role"] == "admin"


def test_map_skips_inactive():
    assert map_erp_user({"id": "1", "is_active": False, "email": "a@b.c", "role": {"name": "HR"}}) is None


def test_map_erp_users_dedupes():
    raw = [
        {"id": "1", "is_active": True, "email": "a@b.c", "name": "A", "role": {"name": "HR"}},
        {"id": "1", "is_active": True, "email": "a@b.c", "name": "A", "role": {"name": "HR"}},
    ]
    assert len(map_erp_users(raw)) == 1


def test_normalize_bare_list():
    client = ErpClient(base_url="https://erp.example.com")
    users, nxt = client._normalize_page([{"id": "1"}])
    assert len(users) == 1
    assert nxt is None


def test_normalize_paginated_results():
    client = ErpClient(base_url="https://erp.example.com")
    users, nxt = client._normalize_page({"results": [{"id": "1"}], "next": "/api/v2/users/?page=2"})
    assert len(users) == 1
    assert nxt == "/api/v2/users/?page=2"


def test_as_role_accepts_new_erp_roles():
    assert _as_role("manager") is AdminRoles.manager
    assert _as_role(AdminRoles.dept_leader) is AdminRoles.dept_leader
    assert _as_role("hr") is AdminRoles.hr


@pytest.mark.asyncio
async def test_erp_client_list_users_paginates(monkeypatch):
    client = ErpClient(base_url="https://erp.example.com")

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    calls = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            calls.append(url)
            if "page=2" in url:
                return FakeResponse({"results": [{"id": "2", "is_active": True, "role": {"name": "Админ"}}]})
            return FakeResponse(
                {
                    "results": [{"id": "1", "is_active": True, "role": {"name": "Менеджер"}}],
                    "next": "/api/v2/users/?page=2",
                }
            )

    monkeypatch.setattr("app.erp.client.httpx.AsyncClient", FakeAsyncClient)
    users = await client.list_users()
    assert len(users) == 2
    assert len(calls) == 2
    assert calls[0].endswith("/api/v2/users/")


@pytest.mark.asyncio
async def test_sync_users_from_erp_is_noop():
    db = MagicMock()
    result = await sync_users_from_erp(db, erp=MagicMock())
    assert result["created"] == 0
    assert "deprecated" in result["errors"]


@pytest.mark.asyncio
async def test_apply_erp_user_batch_is_noop():
    db = MagicMock()
    users = [
        {
            "erp_user_id": "u-1",
            "username": "m@ex.com",
            "full_name": "М",
            "role": "manager",
            "department": None,
        }
    ]
    result = await apply_erp_user_batch(db, users)
    assert result["created"] == 0
    assert result["skipped"] == 1


def test_default_aliases_cover_erp_seed_names():
    erp_seed = {
        "superadmin",
        "админ",
        "менеджер",
        "руководитель",
        "старший менеджер",
        "руководитель отдела",
    }
    for name in erp_seed:
        assert name in DEFAULT_ERP_ROLE_ALIASES
        assert DEFAULT_ERP_ROLE_ALIASES[name] in ALLOWED_ROLES
