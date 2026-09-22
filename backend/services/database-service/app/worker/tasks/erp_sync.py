"""Periodic: ERP → panel users sync (create-only)."""
from __future__ import annotations

from app.config import ERP_SYNC_INTERVAL_MINUTES
from app.worker.huey import huey
from app.worker.jobs import run_erp_user_sync
from app.worker.runtime import run_async
from app.worker.schedule import interval_crontab


@huey.periodic_task(
    interval_crontab(ERP_SYNC_INTERVAL_MINUTES),
    name="hr.erp_users_sync.tick",
)
def tick_erp_user_sync() -> None:
    return run_async(run_erp_user_sync())
