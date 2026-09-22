from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.v1.enums import HiringRequestStatus
from app.schemas.v1.hiring_request import EmployeeRequestUpdate, HiringRequestStatusChange


def _db_with_request(req):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = req
    db.execute.return_value = result
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_return_for_clarification_requires_comment():
    from app.endpoints.v1.hiring_request import change_status_hiring_request_endpoint

    req = MagicMock(id=7, status=HiringRequestStatus.created)
    db = _db_with_request(req)
    with pytest.raises(HTTPException) as exc:
        await change_status_hiring_request_endpoint(
            7, None, HiringRequestStatusChange(status=HiringRequestStatus.returned), db, ("hr-1", "HR")
        )
    assert exc.value.status_code == 422
    assert req.status == HiringRequestStatus.created


@pytest.mark.asyncio
async def test_return_records_comment_and_append_only_history():
    from app.endpoints.v1.hiring_request import change_status_hiring_request_endpoint

    req = MagicMock(id=7, status=HiringRequestStatus.created)
    db = _db_with_request(req)
    with patch("app.endpoints.v1.hiring_request.write_audit", new=AsyncMock()), patch(
        "app.endpoints.v1.hiring_request._to_read", side_effect=lambda value: value
    ):
        await change_status_hiring_request_endpoint(
            7, None,
            HiringRequestStatusChange(status=HiringRequestStatus.returned, comment="Уточните график"),
            db, ("hr-1", "Анна HR"),
        )
    assert req.status == HiringRequestStatus.returned
    assert req.return_comment == "Уточните график"
    history = db.add.call_args.args[0]
    assert history.event_type == "status_changed"
    assert history.actor_name == "Анна HR"
    assert history.comment == "Уточните график"


@pytest.mark.asyncio
@pytest.mark.parametrize("target", [HiringRequestStatus.closed, HiringRequestStatus.cancelled])
async def test_closing_and_cancellation_require_separate_reason(target):
    from app.endpoints.v1.hiring_request import change_status_hiring_request_endpoint

    req = MagicMock(id=8, status=HiringRequestStatus.approved)
    db = _db_with_request(req)
    with pytest.raises(HTTPException) as exc:
        await change_status_hiring_request_endpoint(
            8, None, HiringRequestStatusChange(status=target), db, (None, None)
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_invalid_status_transition_is_rejected():
    from app.endpoints.v1.hiring_request import change_status_hiring_request_endpoint

    req = MagicMock(id=9, status=HiringRequestStatus.created)
    db = _db_with_request(req)
    with pytest.raises(HTTPException) as exc:
        await change_status_hiring_request_endpoint(
            9, None,
            HiringRequestStatusChange(status=HiringRequestStatus.published),
            db, (None, None),
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_condition_edit_history_contains_old_and_new_values():
    from app.endpoints.v1.hiring_request import update_hiring_request_endpoint

    req = MagicMock(id=10, status=HiringRequestStatus.returned, position="Логист")
    db = AsyncMock()
    db.get.return_value = req
    db.add = MagicMock()
    db.flush = AsyncMock()
    with patch("app.endpoints.v1.hiring_request.write_audit", new=AsyncMock()), patch(
        "app.endpoints.v1.hiring_request._to_read", side_effect=lambda value: value
    ):
        await update_hiring_request_endpoint(
            10, EmployeeRequestUpdate(position="Старший логист"), db, ("m-1", "Руководитель")
        )
    history = db.add.call_args.args[0]
    assert history.event_type == "conditions_updated"
    assert history.changes["position"] == {"from": "Логист", "to": "Старший логист"}


@pytest.mark.asyncio
async def test_manager_resubmit_does_not_assign_manager_as_hr():
    from app.endpoints.v1.hiring_request import change_status_hiring_request_endpoint

    req = MagicMock(id=11, status=HiringRequestStatus.returned)
    req.assigned_hr_id = None
    req.assigned_hr_name = None
    db = _db_with_request(req)
    with patch("app.endpoints.v1.hiring_request.write_audit", new=AsyncMock()), patch(
        "app.endpoints.v1.hiring_request._to_read", side_effect=lambda value: value
    ):
        await change_status_hiring_request_endpoint(
            11, None, HiringRequestStatusChange(status=HiringRequestStatus.on_analysis),
            db, ("manager-1", "Руководитель"),
        )
    assert req.status == HiringRequestStatus.on_analysis
    assert req.assigned_hr_id is None
    assert req.assigned_hr_name is None


def test_workflow_migration_contains_history_and_restrict_delete():
    sql = Path(__file__).resolve().parents[1].joinpath("migrations/hiring_request_workflow.sql").read_text("utf-8")
    assert "hiring_request_history" in sql
    assert "ON DELETE RESTRICT" in sql
