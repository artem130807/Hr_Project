"""HTTP process must not run background jobs.

Job bodies live in ``app.worker.jobs`` and are scheduled by Huey in the
worker process. This module keeps the historical function names for tests
and any leftover imports.
"""
from app.app_logging import logger
from app.worker.jobs import run_erp_user_sync as safe_erp_user_sync
from app.worker.jobs import run_status_update as safe_status_update

__all__ = ["init_scheduler", "safe_erp_user_sync", "safe_status_update"]


def init_scheduler():
    logger.info(
        "API process does not start background jobs; "
        "run `huey_consumer app.worker.app.huey` (hr-worker)"
    )
