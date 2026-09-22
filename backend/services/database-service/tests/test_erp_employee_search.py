"""ERP employee directory search for events autocomplete (name / telegram)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.endpoints.v1 import events as events_mod
from app.erp.mapper import (
    find_erp_user_id_by_telegram,
    map_erp_directory_user,
    search_erp_directory_users,
)


def test_map_directory_user_skips_inactive_and_empty():
    assert map_erp_directory_user({"id": "1", "name": "A", "is_active": False}) is None
    assert map_erp_directory_user({"id": "1", "is_active": True}) is None
    assert map_erp_directory_user({"id": "1", "name": "  ", "is_active": True}) is None


def test_map_directory_user_includes_tg_username():
    item = map_erp_directory_user(
        {"id": "1", "name": "Иван", "tg_username": "ivan_hr", "is_active": True}
    )
    assert item["tg_username"] == "@ivan_hr"
    assert item["full_name"] == "Иван"


def test_map_directory_user_telegram_only():
    item = map_erp_directory_user({"id": "1", "tg_username": "@only_tg", "is_active": True})
    assert item["tg_username"] == "@only_tg"
    assert item["full_name"] is None


def test_search_ranks_prefix_and_filters_roles_not_required():
    raw = [
        {"id": "1", "name": "Иванов Иван", "email": "ivan@ex.com", "is_active": True, "role": {"name": "Unknown"}},
        {"id": "2", "name": "Петров Пётр", "email": "petr@ex.com", "is_active": True},
        {"id": "3", "name": "Сидоров Иван", "email": "sid@ex.com", "is_active": True},
        {"id": "4", "name": "Иванова Мария", "email": "maria@ex.com", "is_active": False},
    ]
    items = search_erp_directory_users(raw, query="иван", limit=10)
    assert [i["full_name"] for i in items] == ["Иванов Иван", "Сидоров Иван"]
    assert items[0]["erp_user_id"] == "1"


def test_search_by_telegram_username():
    raw = [
        {"id": "1", "name": "Иванов", "tg_username": "@ivan_hr", "is_active": True},
        {"id": "2", "name": "Петров", "tg_username": "petrov_tg", "is_active": True},
        {"id": "3", "name": "Сидоров", "tg_username": "@ivanov_sid", "is_active": True},
        {"id": "4", "name": "Без тг", "is_active": True},
    ]
    items = search_erp_directory_users(raw, query="@ivan", limit=10, by="telegram")
    assert [i["tg_username"] for i in items] == ["@ivan_hr", "@ivanov_sid"]
    assert items[0]["full_name"] == "Иванов"


def test_find_erp_user_id_by_telegram_exact():
    raw = [
        {"id": "u-ivan", "name": "Иванов", "tg_username": "@ivan_hr", "is_active": True},
        {"id": "u-petr", "name": "Петров", "tg_username": "petrov_tg", "is_active": True},
    ]
    assert find_erp_user_id_by_telegram(raw, "ivan_hr") == "u-ivan"
    assert find_erp_user_id_by_telegram(raw, "@petrov_tg") == "u-petr"
    assert find_erp_user_id_by_telegram(raw, "@unknown") is None
    assert find_erp_user_id_by_telegram(raw, "") is None


@pytest.mark.asyncio
async def test_search_event_employees_endpoint():
    with patch.object(events_mod, "ERP_BASE", "https://erp.example.com"), patch.object(
        events_mod.ErpClient,
        "list_users",
        new=AsyncMock(
            return_value=[
                {
                    "id": "u-1",
                    "name": "Елена Иванова",
                    "email": "e@ex.com",
                    "tg_username": "@elena_hr",
                    "is_active": True,
                },
                {"id": "u-2", "name": "Олег Петров", "email": "o@ex.com", "is_active": True},
            ]
        ),
    ):
        by_name = await events_mod.search_event_employees(q="елен", limit=5, by="name")
        by_tg = await events_mod.search_event_employees(q="elena", limit=5, by="telegram")

    assert len(by_name) == 1
    assert by_name[0]["full_name"] == "Елена Иванова"
    assert by_name[0]["tg_username"] == "@elena_hr"
    assert len(by_tg) == 1
    assert by_tg[0]["tg_username"] == "@elena_hr"


@pytest.mark.asyncio
async def test_search_event_employees_requires_erp_base():
    with patch.object(events_mod, "ERP_BASE", ""):
        with pytest.raises(HTTPException) as exc:
            await events_mod.search_event_employees(q="иван", limit=5, by="name")
    assert exc.value.status_code == 503
