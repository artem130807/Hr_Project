"""Audit trail and candidate stage history helpers."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.v1.models import AuditLog, CandidateStageHistory


async def write_audit(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: str | None = None,
    actor_id: str | None = None,
    actor_name: str | None = None,
    commit: bool = False,
) -> AuditLog:
    row = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=(details or "")[:4000] if details else None,
        actor_id=actor_id,
        actor_name=actor_name,
    )
    db.add(row)
    if commit:
        await db.commit()
        await db.refresh(row)
    else:
        await db.flush()
    return row


async def record_stage_change(
    db: AsyncSession,
    *,
    candidate_id: int,
    from_stage: Any = None,
    to_stage: Any = None,
    from_status: Any = None,
    to_status: Any = None,
    actor_id: str | None = None,
    actor_name: str | None = None,
    comment: str | None = None,
    commit: bool = False,
) -> CandidateStageHistory:
    def _val(v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(getattr(v, "value", v))

    row = CandidateStageHistory(
        candidate_id=candidate_id,
        from_stage=_val(from_stage),
        to_stage=_val(to_stage),
        from_status=_val(from_status),
        to_status=_val(to_status),
        actor_id=actor_id,
        actor_name=actor_name,
        comment=comment,
    )
    db.add(row)
    if commit:
        await db.commit()
        await db.refresh(row)
    else:
        await db.flush()
    return row
