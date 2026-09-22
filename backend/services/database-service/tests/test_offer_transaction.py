from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.endpoints.v1 import messages
from app.schemas.v1.messages import SendOfferData
from app.services.candidate_documents import create_invite


@pytest.mark.asyncio
@pytest.mark.parametrize("commit_fails", [False, True])
async def test_document_link_is_committed_before_external_delivery(monkeypatch, commit_fails):
    db = MagicMock()
    db.get = AsyncMock(return_value=SimpleNamespace(id=1))
    db.execute = AsyncMock(return_value=MagicMock())
    db.execute.return_value.scalar_one_or_none.return_value = None
    db.commit = AsyncMock(side_effect=RuntimeError("commit failed") if commit_fails else None)
    monkeypatch.setattr(messages, "create_invite", AsyncMock(return_value=(object(), "token")))
    monkeypatch.setattr(messages, "build_public_url", lambda *args: "https://hr.test/documents/token")

    async def deliver(*args, **kwargs):
        db.commit.assert_awaited_once()
        assert "https://hr.test/documents/token" in kwargs["message"]
        return {"status": "ok"}

    delivery = AsyncMock(side_effect=deliver)
    monkeypatch.setattr(messages, "sync_candidate_hh_action", delivery)
    data = SendOfferData(candidate_id=1, offer_text="Offer", include_documents_link=True)
    if commit_fails:
        with pytest.raises(RuntimeError, match="commit failed"):
            await messages.send_offer_endpoint(data, MagicMock(), db, None, None)
        delivery.assert_not_awaited()
    else:
        result = await messages.send_offer_endpoint(data, MagicMock(), db, None, None)
        assert result["documents_url"] == "https://hr.test/documents/token"


@pytest.mark.asyncio
async def test_replacement_invite_flushes_revocation_before_insert():
    old = SimpleNamespace(revoked_at=None)
    results = [MagicMock(), MagicMock(), MagicMock()]
    results[1].scalar_one_or_none.return_value = None
    results[2].scalars.return_value.all.return_value = [old]
    db = MagicMock()
    db.execute = AsyncMock(side_effect=results)
    db.flush = AsyncMock()

    def add(invite):
        assert old.revoked_at is not None
        db.flush.assert_awaited_once()

    db.add.side_effect = add
    invite, token = await create_invite(db, SimpleNamespace(id=1), actor_id=None)
    assert invite.candidate_id == 1
    assert token and token != invite.token_hash
    assert db.flush.await_count == 2
