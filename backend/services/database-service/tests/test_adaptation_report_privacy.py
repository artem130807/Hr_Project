from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from app.adaptation.reports import manager_safe_report
from app.adaptation.documents import document_lines
from app.endpoints.v1.adaptation import _authorized_document


@pytest.mark.parametrize("summary", [None, "Согласованный текст"])
def test_manager_output_never_falls_back_to_private_notes(summary):
    row = {"answers": [{"role": "hr", "payload": {
        "hr_comment": "PRIVATE_COMMENT", "hr_notes": "PRIVATE_LEGACY", "manager_summary": summary,
    }}]}
    output = str(manager_safe_report(row)) + str(document_lines(row, "manager_safe"))
    assert "PRIVATE" not in output
    if summary:
        assert summary in output


@pytest.mark.asyncio
@pytest.mark.parametrize("key,final,allowed", [(None, True, False), ("old", True, False),
                                              ("safe2:new", False, False), ("safe2:new", True, True)])
async def test_manager_cannot_download_legacy_or_draft_binary(key, final, allowed):
    row = SimpleNamespace(enrollment_id=1, document_type="manager_safe", generation_key=key, is_final=final)
    db = SimpleNamespace(get=AsyncMock(side_effect=[row, SimpleNamespace(manager_user_id="leader-1")]))
    claims = {"role": "leader", "user_id": "leader-1"}
    if allowed:
        assert await _authorized_document(1, db, claims) is row
    else:
        with pytest.raises(HTTPException) as exc:
            await _authorized_document(1, db, claims)
        assert exc.value.status_code == 403
