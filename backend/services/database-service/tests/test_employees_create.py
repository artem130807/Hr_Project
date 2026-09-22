"""Unit tests for POST /employees create endpoint."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.endpoints.v1 import employees as mod
from app.schemas.v1.hr_ops import EmployeeCreate, EmployeeUpdate


@pytest.mark.asyncio
async def test_create_employee_defaults_date_hired_and_hobbies():
    body = EmployeeCreate(
        full_name="Иванов Иван",
        department="логистический",
        position="Логист",
        phone_number="+7999",
    )
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch.object(mod, "Employee") as Model, patch.object(mod, "write_audit", new_callable=AsyncMock):
        instance = MagicMock()
        instance.id = 11
        instance.full_name = "Иванов Иван"
        Model.return_value = instance

        row = await mod.create_employee(body, db)

    assert row.id == 11
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    kwargs = Model.call_args.kwargs
    assert kwargs["full_name"] == "Иванов Иван"
    assert kwargs["department"] == "логистический"
    assert kwargs["position"] == "Логист"
    assert kwargs["date_hired"] == date.today()
    assert kwargs["hobbies"] == []
    assert kwargs["phone_number"] == "+7999"


@pytest.mark.asyncio
async def test_create_employee_keeps_explicit_date_hired():
    body = EmployeeCreate(
        full_name="Петров",
        department="hr",
        position="HR",
        date_hired=date(2026, 1, 15),
        hobbies=["спорт"],
    )
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch.object(mod, "Employee") as Model, patch.object(mod, "write_audit", new_callable=AsyncMock):
        Model.return_value = MagicMock(id=2)
        await mod.create_employee(body, db)

    kwargs = Model.call_args.kwargs
    assert kwargs["date_hired"] == date(2026, 1, 15)
    assert kwargs["hobbies"] == ["спорт"]


@pytest.mark.asyncio
async def test_hr_can_update_employee_work_start_date():
    employee = MagicMock(id=7, date_hired=date(2026, 1, 10), date_fired=None)
    db = MagicMock()
    db.get = AsyncMock(return_value=employee)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()

    with patch.object(mod, "ERP_BASE", ""), patch.object(
        mod, "reschedule_active_adaptation_for_start_date", new_callable=AsyncMock
    ) as adaptation_sync, patch.object(
        mod, "write_audit", new_callable=AsyncMock
    ):
        result = await mod.update_employee(
            7,
            EmployeeUpdate(date_hired=date(2026, 2, 3)),
            db,
            claims={"sub": "hr@example.ru", "role": "hr"},
        )

    assert result is employee
    assert employee.date_hired == date(2026, 2, 3)
    adaptation_sync.assert_awaited_once_with(
        db, employee_id=7, value=date(2026, 2, 3)
    )
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_employee_work_start_date_cannot_be_cleared():
    employee = MagicMock(id=7, date_hired=date(2026, 1, 10), date_fired=None)
    db = MagicMock()
    db.get = AsyncMock(return_value=employee)

    with pytest.raises(mod.HTTPException) as exc:
        await mod.update_employee(
            7,
            EmployeeUpdate(date_hired=None),
            db,
            claims={"sub": "hr@example.ru", "role": "hr"},
        )

    assert exc.value.status_code == 422
    assert "обязательна" in exc.value.detail


@pytest.mark.asyncio
async def test_employee_work_start_date_cannot_be_after_termination_date():
    employee = MagicMock(
        id=7,
        date_hired=date(2026, 1, 10),
        date_fired=date(2026, 2, 1),
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=employee)

    with pytest.raises(mod.HTTPException) as exc:
        await mod.update_employee(
            7,
            EmployeeUpdate(date_hired=date(2026, 2, 2)),
            db,
            claims={"sub": "hr@example.ru", "role": "hr"},
        )

    assert exc.value.status_code == 422
    assert "увольнения" in exc.value.detail


@pytest.mark.asyncio
async def test_non_hr_cannot_update_employee():
    db = MagicMock()
    db.get = AsyncMock()

    with pytest.raises(mod.HTTPException) as exc:
        await mod.update_employee(
            7,
            EmployeeUpdate(date_hired=date(2026, 2, 3)),
            db,
            claims={"sub": "leader@example.ru", "role": "leader"},
        )

    assert exc.value.status_code == 403
    db.get.assert_not_awaited()
