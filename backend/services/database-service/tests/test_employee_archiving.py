from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.endpoints.v1 import employees as mod


@pytest.mark.asyncio
async def test_delete_employee_archives_and_preserves_references():
    employee = MagicMock(id=7, full_name="Иванов Иван", archived_at=None)
    db = MagicMock()
    db.get = AsyncMock(return_value=employee)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.delete = AsyncMock()

    with patch.object(mod, "write_audit", new=AsyncMock()) as audit:
        result = await mod.delete_employee(
            7, db, claims={"sub": "hr@example.ru", "role": "hr"}
        )

    assert result is None
    assert employee.archived_at is not None
    assert db.execute.await_count == 3  # contacts, adaptation and VNR
    db.delete.assert_not_awaited()
    db.commit.assert_awaited_once()
    assert audit.await_args.kwargs["action"] == "employee.archive"


@pytest.mark.asyncio
async def test_delete_employee_is_idempotent_when_already_archived():
    employee = MagicMock(id=7, archived_at=MagicMock())
    db = MagicMock()
    db.get = AsyncMock(return_value=employee)
    db.execute = AsyncMock()
    db.commit = AsyncMock()

    assert await mod.delete_employee(
        7, db, claims={"sub": "hr@example.ru", "role": "hr"}
    ) is None
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_hr_cannot_archive_employee():
    db = MagicMock()
    db.get = AsyncMock()
    with pytest.raises(mod.HTTPException) as exc:
        await mod.delete_employee(
            7, db, claims={"sub": "leader@example.ru", "role": "leader"}
        )
    assert exc.value.status_code == 403
    db.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_employee_list_excludes_archived_rows():
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)

    await mod.list_employees(db=db)

    statement = db.execute.await_args.args[0]
    assert "employees.archived_at IS NULL" in str(statement)


def test_employee_archiving_migration_is_idempotent():
    sql = Path(__file__).resolve().parents[1].joinpath(
        "migrations/employee_archiving.sql"
    ).read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS archived_at" in sql
    assert "CREATE INDEX IF NOT EXISTS" in sql
