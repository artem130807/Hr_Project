from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.endpoints.v1 import candidate_documents as api


class ExpiringRow(SimpleNamespace):
    expired = False

    def __getattribute__(self, name):
        if not name.startswith("_") and name != "expired" and self.expired:
            raise AssertionError("ORM attribute accessed after commit")
        return super().__getattribute__(name)


@pytest.mark.asyncio
async def test_invitation_response_does_not_reload_after_commit(monkeypatch):
    candidate = ExpiringRow(id=7)
    invite = ExpiringRow(id=9, expires_at=datetime.now(timezone.utc))
    db = MagicMock()
    db.get = AsyncMock(return_value=candidate)

    async def commit():
        candidate.expired = invite.expired = True

    db.commit = AsyncMock(side_effect=commit)
    monkeypatch.setattr(api, "create_invite", AsyncMock(return_value=(invite, "token")))
    monkeypatch.setattr(api, "write_audit", AsyncMock())
    monkeypatch.setattr(api, "build_public_url", lambda *args: "https://hr.test/documents/token")
    result = await api.generate_candidate_documents_invite(
        7, MagicMock(), db, {"user_id": "hr-user", "role": "hr"},
    )
    assert result["candidate_id"] == 7
    assert result["expires_at"]
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_draft_response_prepared_before_commit(monkeypatch):
    session = ExpiringRow(id=1, expires_at=datetime.now(timezone.utc))
    db = MagicMock()
    rows = MagicMock()
    rows.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=rows)

    async def commit():
        session.expired = True

    db.commit = AsyncMock(side_effect=commit)
    monkeypatch.setattr(api, "resolve_invite", AsyncMock(return_value=object()))
    monkeypatch.setattr(api, "create_upload_session", AsyncMock(return_value=(session, "secret-token")))
    result = await api.open_candidate_documents_upload_session(
        "invite-token", {}, SimpleNamespace(headers={}), db,
    )
    assert result["session_token"] == "secret-token"
    assert result["files"] == []
    db.commit.assert_awaited_once()
