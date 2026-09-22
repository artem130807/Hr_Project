from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.v1.enums import CandidateStage


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", list(CandidateStage))
async def test_candidate_delete_archives_every_stage_and_preserves_history(stage):
    from app.endpoints.v1 import candidates as mod

    candidate = MagicMock(id=6, stage=stage, archived_at=None)
    db = MagicMock()
    db.get = AsyncMock(return_value=candidate)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.delete = AsyncMock()

    with patch.object(mod, "write_audit", new=AsyncMock()) as audit:
        result = await mod.delete_candidate_endpoint(6, db)

    assert result is None
    assert isinstance(candidate.archived_at, datetime)
    assert db.execute.await_count == 3
    db.delete.assert_not_awaited()
    assert db.commit.await_count == 2
    db.rollback.assert_not_awaited()
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_candidate_delete_is_idempotent():
    from app.endpoints.v1 import candidates as mod

    candidate = MagicMock(id=6, archived_at=datetime.now().astimezone())
    db = MagicMock()
    db.get = AsyncMock(return_value=candidate)
    db.execute = AsyncMock()
    db.commit = AsyncMock()

    assert await mod.delete_candidate_endpoint(6, db) is None
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


def test_candidate_archiving_migration_is_registered():
    from pathlib import Path

    service_root = Path(__file__).resolve().parents[1]
    migration = service_root / "migrations" / "candidate_archiving.sql"
    main_source = (service_root / "main.py").read_text(encoding="utf-8")

    assert migration.is_file()
    assert "ADD COLUMN IF NOT EXISTS archived_at" in migration.read_text(encoding="utf-8")
    assert "candidate_archiving.sql" in main_source


@pytest.mark.asyncio
async def test_candidate_archive_succeeds_when_optional_cleanup_fails():
    from sqlalchemy.exc import ProgrammingError
    from app.endpoints.v1 import candidates as mod

    candidate = MagicMock(id=6, stage=CandidateStage.employment, archived_at=None)
    db = MagicMock()
    db.get = AsyncMock(return_value=candidate)
    db.execute = AsyncMock(side_effect=ProgrammingError("UPDATE", {}, Exception("legacy table")))
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    assert await mod.delete_candidate_endpoint(6, db) is None
    assert candidate.archived_at is not None
    db.commit.assert_awaited_once()
    db.rollback.assert_awaited_once()
