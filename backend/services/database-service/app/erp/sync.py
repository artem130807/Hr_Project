"""Legacy ERP→local panel user sync — removed (users live in ERP only)."""
from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.app_logging import logger


async def apply_erp_user_batch(db: AsyncSession, users: Sequence[Any]) -> dict:
    logger.warning("apply_erp_user_batch is a no-op: local panel users were removed")
    return {"created": 0, "skipped": len(list(users or [])), "errors": []}


async def sync_users_from_erp(db: AsyncSession, erp=None) -> dict:
    logger.warning("sync_users_from_erp is a no-op: local panel users were removed")
    return {"created": 0, "skipped": 0, "errors": ["deprecated"]}


def _as_role(value: Any):
    from app.db.v1.enums import AdminRoles

    if isinstance(value, AdminRoles):
        return value
    return AdminRoles(str(value))
