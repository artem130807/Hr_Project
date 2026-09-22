from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.v1.models import CandidateDocumentUploadSession
from app.endpoints.v1 import candidate_documents as api
from app.services.candidate_documents import hash_token, resolve_upload_session, resolve_invite


@pytest.mark.asyncio
@pytest.mark.parametrize("used,revoked,expired,allow,accepted", [
    (True, False, False, True, True),
    (True, False, False, False, False),
    (True, True, False, True, False),
    (True, False, True, True, False),
    (False, False, False, False, True),
])
async def test_receipt_retry_never_bypasses_revocation_or_expiry(used, revoked, expired, allow, accepted):
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(used_at=now if used else None, revoked_at=now if revoked else None,
                          expires_at=now + timedelta(hours=-1 if expired else 1))
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    if accepted:
        assert await resolve_invite(db, "token", allow_used=allow) is row
    else:
        with pytest.raises(HTTPException) as exc:
            await resolve_invite(db, "token", allow_used=allow)
        assert exc.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["submitted", "complete"])
async def test_submit_retry_returns_receipt_without_storage_writes(monkeypatch, status):
    now = datetime.now(timezone.utc)
    invite = SimpleNamespace(id=1, candidate_id=2, used_at=now)
    session = SimpleNamespace(status="submitted")
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = SimpleNamespace(id=4, status=status, submitted_at=now)
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    copy = AsyncMock()
    monkeypatch.setattr(api, "resolve_invite", AsyncMock(return_value=invite))
    monkeypatch.setattr(api, "resolve_upload_session", AsyncMock(return_value=session))
    monkeypatch.setattr(api, "move_draft_package", copy)
    receipt = await api.submit_candidate_document_upload_session(
        "invite", {"session_token": "session"}, SimpleNamespace(headers={}), db,
    )
    assert receipt == {"id": 4, "status": status, "submitted_at": now}
    copy.assert_not_awaited()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_another_draft_cannot_reuse_consumed_invite(monkeypatch):
    monkeypatch.setattr(api, "resolve_invite", AsyncMock(return_value=SimpleNamespace(used_at=True)))
    monkeypatch.setattr(api, "resolve_upload_session", AsyncMock(return_value=SimpleNamespace(status="draft")))
    db = MagicMock()
    with pytest.raises(HTTPException) as exc:
        await api.submit_candidate_document_upload_session(
            "invite", {"session_token": "other"}, SimpleNamespace(headers={}), db,
        )
    assert exc.value.status_code == 409
    db.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("invite_id,candidate_id,token,allow,accepted", [
    (1, 2, "secret", True, True),
    (1, 2, "secret", False, False),
    (9, 2, "secret", True, False),
    (1, 9, "secret", True, False),
    (1, 2, "wrong", True, False),
])
async def test_submitted_session_real_query_is_scoped(invite_id, candidate_id, token, allow, accepted):
    engine = create_async_engine("sqlite+aiosqlite://")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(CandidateDocumentUploadSession.__table__.create)
        async with factory() as db:
            db.add(CandidateDocumentUploadSession(
                session_id="a" * 32, token_hash=hash_token("secret"), invite_id=1, candidate_id=2,
                status="submitted", expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            ))
            await db.commit()
        async with factory() as db:
            invite = SimpleNamespace(id=invite_id, candidate_id=candidate_id)
            if accepted:
                row = await resolve_upload_session(db, invite, token, allow_submitted=allow)
                assert row.status == "submitted"
            else:
                with pytest.raises(HTTPException) as exc:
                    await resolve_upload_session(db, invite, token, allow_submitted=allow)
                assert exc.value.status_code == 404
    finally:
        await engine.dispose()
