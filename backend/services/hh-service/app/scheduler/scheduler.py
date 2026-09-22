from datetime import datetime, timezone

from app.tasks.autosearch import autosearch
from app.tasks.auto_reject_filtered import auto_reject_filtered
from app.scheduler.lock import DistributedLock
from app.app_logging import logger
import app.config as conf

_KEEPALIVE_REMAINING_SECONDS = 2 * 3600


async def safe_autosearch():
    async with DistributedLock("autosearch_lock", ttl=3600) as acquired:
        if not acquired:
            logger.info("Autosearch skipped — another instance is running")
            return
        logger.info("Autosearch started")
        from app.dependencies import get_ai_client, get_db_client, get_hh_client

        await autosearch(
            await get_db_client(),
            await get_hh_client(),
            await get_ai_client(),
        )
        logger.info("Autosearch finished")


async def safe_auto_reject_filtered():
    interval = conf.AUTO_REJECT_INTERVAL_MINUTES
    lock_ttl = max(60, interval * 60 - 15)
    async with DistributedLock("auto_reject_filtered_lock", ttl=lock_ttl) as acquired:
        if not acquired:
            logger.info("auto_reject_filtered skipped — another instance is running")
            return
        logger.info(
            "auto_reject_filtered started (batch=%s every %s min)",
            conf.AUTO_REJECT_BATCH_SIZE,
            interval,
        )
        from app.dependencies import get_db_client, get_hh_client

        await auto_reject_filtered(await get_db_client(), await get_hh_client())
        logger.info("auto_reject_filtered finished")


def _seconds_until_expiry(token_expires) -> float:
    if token_expires is None:
        return 0.0
    expires = token_expires
    if getattr(expires, "tzinfo", None) is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return (expires - datetime.now(timezone.utc)).total_seconds()


async def safe_token_keepalive():
    """Proactive HH refresh so the rotating refresh_token does not go idle past TTL."""
    async with DistributedLock("hh_token_keepalive_lock", ttl=600) as acquired:
        if not acquired:
            logger.info("HH token keepalive skipped — another instance is running")
            return
        from app.dependencies import get_hh_client

        tm = (await get_hh_client()).token_manager
        if not tm.refresh_token:
            logger.warning("HH token keepalive: no refresh_token")
            return
        remaining = _seconds_until_expiry(tm.token_expires)
        if remaining > _KEEPALIVE_REMAINING_SECONDS:
            logger.info("HH token keepalive: access token still valid (%.0fs left)", remaining)
            return
        logger.info("HH token keepalive: refreshing")
        try:
            await tm._refresh_tokens()
        except Exception as e:
            logger.warning("HH token keepalive: refresh failed: %s", e)


def init_scheduler():
    logger.info(
        "HH API process does not start a scheduler; "
        "periodic jobs are triggered by hr-worker via /v1/internal/jobs/*"
    )
