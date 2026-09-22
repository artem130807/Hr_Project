from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from app.db.v1.models import Employee
from app.schemas.v1.admins import AdminUserUpdate
from app.schemas.v1.hr_ops import EmployeeUpdate
from app.services.employee_start_date_sync import (
    push_hr_date_to_erp,
    reschedule_active_adaptation_for_start_date,
    resolve_erp_user_id,
)


def _employee(**overrides):
    values = {
        "id": 7,
        "erp_user_id": None,
        "full_name": "Иванов Иван Иванович",
        "date_hired": date(2026, 9, 1),
        "date_fired": None,
    }
    values.update(overrides)
    return Employee(**values)


def _request():
    return Request({"type": "http", "method": "PATCH", "path": "/", "headers": []})


@pytest.mark.asyncio
async def test_hr_to_erp_uses_stable_link_without_directory_search():
    employee = _employee(erp_user_id="erp-7")
    client = MagicMock()
    client.list_users = AsyncMock()
    client.update_user = AsyncMock(return_value={"id": "erp-7"})

    erp_id = await push_hr_date_to_erp(
        employee, date(2026, 9, 22), client=client, access_token="token"
    )

    assert erp_id == "erp-7"
    client.list_users.assert_not_awaited()
    client.update_user.assert_awaited_once_with(
        "erp-7", {"date_hired": "2026-09-22"}, access_token="token"
    )


@pytest.mark.asyncio
async def test_hr_to_erp_links_only_unique_exact_name_match():
    employee = _employee()
    client = MagicMock()
    client.list_users = AsyncMock(return_value=[
        {"id": "erp-1", "name": "  Иванов   Иван Иванович "},
        {"id": "erp-2", "name": "Другой сотрудник"},
    ])
    client.update_user = AsyncMock(return_value={"id": "erp-1"})

    assert await resolve_erp_user_id(employee, client, access_token="token") == "erp-1"

    client.list_users.return_value = [
        {"id": "erp-1", "name": "Иванов Иван Иванович"},
        {"id": "erp-3", "name": "Иванов Иван Иванович"},
    ]
    assert await resolve_erp_user_id(employee, client, access_token="token") is None


@pytest.mark.asyncio
async def test_start_date_change_reschedules_only_untouched_adaptation_points():
    enrollment = SimpleNamespace(id=4, start_date=date(2026, 9, 1))
    week = SimpleNamespace(
        id=10, kind="week_1", plan_date=date(2026, 9, 8),
        original_plan_date=date(2026, 9, 8), closed=False, fact_date=None,
        forced_completed_at=None, finalized_at=None, rescheduled_at=None,
    )
    answered_month = SimpleNamespace(
        id=11, kind="month_1", plan_date=date(2026, 10, 1),
        original_plan_date=date(2026, 10, 1), closed=False, fact_date=None,
        forced_completed_at=None, finalized_at=None, rescheduled_at=None,
    )
    manually_moved = SimpleNamespace(
        id=12, kind="month_2", plan_date=date(2026, 11, 10),
        original_plan_date=date(2026, 11, 1), closed=False, fact_date=None,
        forced_completed_at=None, finalized_at=None, rescheduled_at=object(),
    )
    extra = SimpleNamespace(
        id=13, kind="extra", plan_date=date(2026, 9, 20),
        original_plan_date=date(2026, 9, 20), closed=False, fact_date=None,
        forced_completed_at=None, finalized_at=None, rescheduled_at=None,
    )

    enrollment_result = MagicMock()
    enrollment_result.scalar_one_or_none.return_value = enrollment.id
    update_enrollment_result = MagicMock()
    checkpoints_result = MagicMock()
    checkpoints_result.all.return_value = [week, answered_month, manually_moved, extra]
    answered_result = MagicMock()
    answered_result.scalars.return_value.all.return_value = [11]
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[
        enrollment_result,
        update_enrollment_result,
        checkpoints_result,
        answered_result,
        MagicMock(),
    ])

    changed = await reschedule_active_adaptation_for_start_date(
        db, employee_id=7, value=date(2026, 9, 15)
    )

    assert changed == 1
    assert db.execute.await_count == 5
    assert answered_month.plan_date == date(2026, 10, 1)
    assert manually_moved.plan_date == date(2026, 11, 10)
    assert extra.plan_date == date(2026, 9, 20)


@pytest.mark.asyncio
async def test_local_employee_update_pushes_same_date_to_erp_and_saves_link():
    from app.endpoints.v1 import employees as mod

    employee = MagicMock(
        id=7, erp_user_id=None, full_name="Иванов Иван",
        date_hired=date(2026, 9, 1), date_fired=None,
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=employee)
    owner_result = MagicMock()
    owner_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=owner_result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    client = MagicMock()
    client.update_user = AsyncMock(return_value={"id": "erp-7"})

    with patch.object(mod, "ERP_BASE", "https://erp.example"), patch.object(
        mod, "ErpClient", return_value=client
    ), patch.object(
        mod, "resolve_erp_user_id", new=AsyncMock(return_value="erp-7")
    ) as resolve, patch.object(
        mod, "reschedule_active_adaptation_for_start_date", new=AsyncMock(return_value=3)
    ) as adaptation_sync, patch.object(mod, "write_audit", new=AsyncMock()):
        await mod.update_employee(
            7, EmployeeUpdate(date_hired=date(2026, 9, 22)), db,
            claims={"sub": "hr@example.ru", "role": "hr"}, token="erp-token",
        )

    resolve.assert_awaited_once()
    adaptation_sync.assert_awaited_once_with(
        db, employee_id=7, value=date(2026, 9, 22)
    )
    assert employee.erp_user_id == "erp-7"
    assert employee.date_hired == date(2026, 9, 22)
    client.update_user.assert_awaited_once_with(
        "erp-7", {"date_hired": "2026-09-22"}, access_token="erp-token"
    )
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_local_employee_update_rejects_duplicate_erp_link_before_remote_write():
    from fastapi import HTTPException
    from app.endpoints.v1 import employees as mod

    employee = MagicMock(
        id=35, erp_user_id=None, full_name="Никифорова Татьяна Станиславовна",
        date_hired=date(2026, 9, 22), date_fired=None,
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=employee)
    owner_result = MagicMock()
    owner_result.scalar_one_or_none.return_value = 12
    db.execute = AsyncMock(return_value=owner_result)
    client = MagicMock()
    client.update_user = AsyncMock()

    with patch.object(mod, "ERP_BASE", "https://erp.example"), patch.object(
        mod, "ErpClient", return_value=client
    ), patch.object(
        mod, "resolve_erp_user_id", new=AsyncMock(return_value="erp-7")
    ):
        with pytest.raises(HTTPException) as error:
            await mod.update_employee(
                35, EmployeeUpdate(date_hired=date(2026, 9, 15)), db,
                claims={"sub": "hr@example.ru", "role": "hr"}, token="erp-token",
            )

    assert error.value.status_code == 409
    client.update_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_erp_employee_update_applies_same_date_to_linked_hr_employee():
    from app.endpoints.v1 import admins as mod

    employee = _employee(erp_user_id="erp-7")
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    client = MagicMock()
    client.update_user = AsyncMock(return_value={
        "id": "erp-7", "email": "i@example.ru", "name": employee.full_name,
        "is_active": True, "role": {"id": 3, "name": "Менеджер"},
        "date_hired": "2026-09-23",
    })

    with patch.object(mod, "ERP_BASE", "https://erp.example"), patch.object(
        mod, "ErpClient", return_value=client
    ), patch.object(
        mod, "find_hr_employee_by_erp_id", new=AsyncMock(return_value=employee)
    ), patch.object(
        mod, "reschedule_active_adaptation_for_start_date", new=AsyncMock(return_value=2)
    ) as adaptation_sync, patch.object(mod, "_negotiation_flags", new=AsyncMock(return_value={})), patch.object(
        mod, "write_audit", new=AsyncMock()
    ):
        result = await mod.update_admin_user_endpoint(
            "erp-7", AdminUserUpdate(date_hired=date(2026, 9, 23)),
            _request(), db, token="erp-token",
        )

    assert employee.date_hired == date(2026, 9, 23)
    adaptation_sync.assert_awaited_once_with(
        db, employee_id=employee.id, value=date(2026, 9, 23)
    )
    assert result["date_hired"] == "2026-09-23"
    client.update_user.assert_awaited_once_with(
        "erp-7", {"date_hired": "2026-09-23"}, access_token="erp-token"
    )
    db.commit.assert_awaited_once()
    db.flush.assert_awaited_once()
    db.rollback.assert_not_awaited()
