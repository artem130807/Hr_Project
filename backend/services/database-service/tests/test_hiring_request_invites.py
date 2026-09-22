from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Response

from app.db.v1.enums import Departments, HiringRequestStatus
from app.schemas.v1.hiring_request import EmployeeRequestCreate
from app.services.hiring_requests import create_request_record, hash_invite_token, public_hiring_request_url


def _request_data(**overrides):
    payload = {
        "position": "Логист",
        "department": Departments.logistics,
        "headcount": 1,
        "manager_name": "Иванов Иван",
        "manager_position": "Руководитель",
        "phone": "+7 900 000-00-00",
        "purpose": "Расширение отдела",
        "mandatory_requirements": ["Опыт работы"],
        "schedule": "5/2",
        "work_format": "офис",
        "status": HiringRequestStatus.published,
    }
    payload.update(overrides)
    return EmployeeRequestCreate(**payload)


def test_hiring_request_invite_token_is_hashed_and_url_uses_frontend(monkeypatch):
    token = "secret/token"
    assert token not in hash_invite_token(token)
    assert len(hash_invite_token(token)) == 64
    monkeypatch.setenv("HR_FRONTEND_BASE_URL", "https://hr.example.ru/v1/")
    request = SimpleNamespace(headers={"Origin": "https://api.example.ru"}, base_url="https://api.example.ru/v1/")
    assert public_hiring_request_url(request, token) == "https://hr.example.ru/hiring-request/secret%2Ftoken"


@pytest.mark.asyncio
async def test_shared_creation_forces_safe_initial_fields():
    stored = {}

    def build_row(**payload):
        row = SimpleNamespace(id=15, **payload)
        stored.update(payload)
        return row

    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    with (
        patch("app.services.hiring_requests.EmployeeRequest", side_effect=build_row),
        patch("app.services.hiring_requests.write_audit", AsyncMock()),
    ):
        await create_request_record(db, _request_data(initiator_name=None))

    assert stored["status"] == HiringRequestStatus.created
    assert stored["initiator_name"] == "Иванов Иван"
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_public_submission_consumes_invite_and_forces_created_status():
    from app.endpoints.v1 import hiring_request as endpoint

    invite = SimpleNamespace(
        id=3,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        used_at=None,
        hiring_request_id=None,
    )
    row = SimpleNamespace(
        id=77,
        manager_name="Иванов Иван",
        status=HiringRequestStatus.created,
    )
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    create = AsyncMock(return_value=row)
    publish = AsyncMock()

    with (
        patch.object(endpoint, "resolve_invite", AsyncMock(return_value=invite)),
        patch.object(endpoint, "create_request_record", create),
        patch.object(endpoint, "publish_request_created", publish),
    ):
        result = await endpoint.submit_public_hiring_request("token", _request_data(), Response(), db)

    assert invite.used_at is not None
    assert invite.hiring_request_id == 77
    create.assert_awaited_once()
    assert create.await_args.kwargs["audit_action"] == "hiring_request.public.create"
    assert create.await_args.args[1].linked_vacancy_id is None
    assert create.await_args.args[1].initiator_name == "Иванов Иван"
    db.commit.assert_awaited_once()
    publish.assert_awaited_once_with(row, actor_id=None, actor_name="Иванов Иван")
    assert result.public_code == "З-77"


def test_public_hiring_request_routes_and_migration_are_registered():
    from main import app

    paths = {(route.path, method) for route in app.routes for method in getattr(route, "methods", set())}
    assert ("/v1/hiring-request-invites", "POST") in paths
    assert ("/v1/public/hiring-request-invites/{token}", "GET") in paths
    assert ("/v1/public/hiring-request-invites/{token}", "POST") in paths
