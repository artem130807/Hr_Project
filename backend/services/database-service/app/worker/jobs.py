"""Async job bodies invoked by Huey tasks (no Huey imports)."""
from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.app_logging import logger
from app.config import (
    AI_EVAL_RELAY_ENABLED,
    CALL_WHISPER_ENABLED,
    CALL_WHISPER_BATCH_SIZE,
    CALL_WHISPER_INTERVAL_MINUTES,
    CALL_WHISPER_REQUEST_DELAY_SECONDS,
    CALL_WHISPER_TIMEOUT,
    DATABASE_URL,
    DB_SCHEMA,
    ERP_API_KEY,
    ERP_BASE,
    ERP_BEARER_TOKEN,
    ERP_SYNC_ENABLED,
    ERP_SYNC_INTERVAL_MINUTES,
    OPENAI_API_TOKEN,
    RABBITMQ_QUEUE_CANDIDATE_EVALUATE_REQUEST,
    RABBITMQ_QUEUE_CANDIDATE_EVALUATE_RESULT,
    RABBITMQ_URL,
    T2_CALL_SYNC_ENABLED,
    T2_CALL_SYNC_INTERVAL_MINUTES,
    T2_STT_BACKFILL_BATCH_SIZE,
    T2_STT_BACKFILL_ENABLED,
    T2_STT_BACKFILL_INTERVAL_MINUTES,
    T2_STT_BACKFILL_REQUEST_DELAY_SECONDS,
    T2_TOKEN_KEEPALIVE_ENABLED,
)
from app.db.database import AsyncSessionLocal
from app.events.dispatcher import dispatch_due_permanent_events
from app.events.expiry import complete_overdue_planner_events
from app.scheduler.lock import DistributedLock


async def run_permanent_events_tick() -> int:
    async with DistributedLock("permanent_hr_events_tick", ttl=50) as acquired:
        if not acquired:
            logger.info("permanent events tick skipped — another worker holds the lock")
            return 0
        async with AsyncSessionLocal() as db:
            sent = await dispatch_due_permanent_events(db)
            if sent:
                logger.info("permanent events dispatched: %s", sent)
            return sent


async def run_complete_overdue_planner_events() -> int:
    async with DistributedLock("hr_planner_events_auto_complete", ttl=120) as acquired:
        if not acquired:
            logger.info("planner event auto-complete skipped — another worker holds the lock")
            return 0
        async with AsyncSessionLocal() as db:
            closed = await complete_overdue_planner_events(db)
            if closed:
                logger.info("planner events auto-completed: %s", closed)
            return closed


async def run_candidate_document_drafts_purge() -> int:
    async with DistributedLock("candidate_document_drafts_purge", ttl=600) as acquired:
        if not acquired:
            return 0
        from app.services.candidate_documents import purge_expired_upload_sessions
        async with AsyncSessionLocal() as db:
            purged = await purge_expired_upload_sessions(db)
            if purged:
                logger.info("expired candidate document drafts purged: %s", purged)
            return purged


async def run_status_update() -> None:
    async with DistributedLock("statuses_update_lock", ttl=1800) as acquired:
        if not acquired:
            logger.info("status update skipped — another worker holds the lock")
            return

        logger.info("Status update started")
        from app.dependencies import get_ai_client, get_hh_client

        hh = await get_hh_client()
        ai = await get_ai_client()
        if hh is None or ai is None:
            logger.warning("status update skipped — HH or AI client is not configured")
            return

        from app.tasks.status_update import update_statuses_task

        async with AsyncSessionLocal() as db:
            await update_statuses_task(db=db, hh=hh, ai=ai)
        logger.info("Status update finished")


async def run_erp_user_sync() -> None:
    if not ERP_SYNC_ENABLED:
        logger.info("ERP user sync disabled (ERP_SYNC_ENABLED=false)")
        return
    if not ERP_BASE:
        logger.warning("ERP user sync skipped — ERP_BASE is not configured")
        return
    if not (ERP_BEARER_TOKEN or ERP_API_KEY):
        logger.warning("ERP user sync skipped — set ERP_BEARER_TOKEN or ERP_API_KEY")
        return

    ttl = max(int(ERP_SYNC_INTERVAL_MINUTES or 60) * 60, 300)
    async with DistributedLock("erp_users_sync_lock", ttl=ttl) as acquired:
        if not acquired:
            logger.info("ERP user sync skipped — another worker holds the lock")
            return
        logger.info("ERP user sync started")
        try:
            from app.erp.sync import sync_users_from_erp

            async with AsyncSessionLocal() as db:
                await sync_users_from_erp(db)
        except Exception as exc:
            logger.exception("ERP user sync failed: %s", exc)
        logger.info("ERP user sync finished")


async def run_t2_call_sync() -> dict:
    if not T2_CALL_SYNC_ENABLED:
        logger.info("T2 call sync disabled (T2_CALL_SYNC_ENABLED=false)")
        return {"skipped_reason": "disabled"}

    ttl = max(int(T2_CALL_SYNC_INTERVAL_MINUTES or 15) * 60, 120)
    async with DistributedLock("t2_call_sync_lock", ttl=ttl) as acquired:
        if not acquired:
            logger.info("T2 call sync skipped — another worker holds the lock")
            return {"skipped_reason": "lock"}
        logger.info("T2 call sync started")
        from app.t2.sync import sync_call_conversations

        async with AsyncSessionLocal() as db:
            stats = await sync_call_conversations(db)
        logger.info("T2 call sync finished: %s", stats)
        return stats


async def run_t2_token_keepalive() -> dict:
    if not T2_TOKEN_KEEPALIVE_ENABLED:
        logger.info("T2 token keepalive disabled (T2_TOKEN_KEEPALIVE_ENABLED=false)")
        return {"skipped_reason": "disabled"}

    async with DistributedLock("t2_token_keepalive_lock", ttl=120) as acquired:
        if not acquired:
            logger.info("T2 token keepalive skipped — another worker holds the lock")
            return {"skipped_reason": "lock"}
        from app.repositories.t2_oauth_token_repository import T2OAuthTokenRepository
        from app.t2.auth import ensure_access_token
        from app.t2.tokens import T2TokenError, should_refresh_access

        async with AsyncSessionLocal() as db:
            repo = T2OAuthTokenRepository(db)
            row = await repo.get()
            payload = row.payload if row is not None and isinstance(row.payload, dict) else None
            if payload is None:
                logger.info("T2 token keepalive skipped — no stored tokens")
                return {"skipped_reason": "no_token"}
            if not should_refresh_access(payload):
                logger.info("T2 token keepalive: access token still valid")
                return {"refreshed": False}
            try:
                token = await ensure_access_token(repo)
            except T2TokenError as exc:
                logger.warning("T2 token keepalive refresh failed: %s", exc)
                return {"refreshed": False, "error": str(exc)}
            return {"refreshed": True, "has_access": bool(token)}


async def run_t2_stt_backfill() -> dict:
    if not T2_STT_BACKFILL_ENABLED:
        logger.info("T2 STT backfill disabled (T2_STT_BACKFILL_ENABLED=false)")
        return {"skipped_reason": "disabled"}

    per_item = 30.0 + float(T2_STT_BACKFILL_REQUEST_DELAY_SECONDS) + 2.0
    ttl = max(
        int(T2_STT_BACKFILL_INTERVAL_MINUTES or 10) * 60,
        int(T2_STT_BACKFILL_BATCH_SIZE * per_item) + 60,
    )
    async with DistributedLock("t2_stt_backfill_lock", ttl=ttl) as acquired:
        if not acquired:
            logger.info("T2 STT backfill skipped — another worker holds the lock")
            return {"skipped_reason": "lock"}
        logger.info("T2 STT backfill started")
        from app.t2.sync import backfill_missing_transcripts

        async with AsyncSessionLocal() as db:
            stats = await backfill_missing_transcripts(db)
        logger.info("T2 STT backfill finished: %s", stats)
        return stats


async def run_call_whisper_classify() -> dict:
    if not CALL_WHISPER_ENABLED:
        logger.info("WhisperAi classify disabled (CALL_WHISPER_ENABLED=false)")
        return {"skipped_reason": "disabled"}

    per_item = float(CALL_WHISPER_TIMEOUT) + float(CALL_WHISPER_REQUEST_DELAY_SECONDS) + 5.0
    ttl = max(
        int(CALL_WHISPER_INTERVAL_MINUTES or 5) * 60,
        int(CALL_WHISPER_BATCH_SIZE * per_item) + 60,
    )
    async with DistributedLock("call_whisper_classify_lock", ttl=ttl) as acquired:
        if not acquired:
            logger.info("WhisperAi classify skipped — another worker holds the lock")
            return {"skipped_reason": "lock"}
        if not OPENAI_API_TOKEN:
            logger.info("WhisperAi classify: no OPENAI_API_TOKEN — heuristics only")
        logger.info("WhisperAi classify started")
        from app.calls.classify import classify_pending_conversations

        async with AsyncSessionLocal() as db:
            stats = await classify_pending_conversations(db)
        logger.info("WhisperAi classify finished: %s", stats)
        return stats


async def run_hh_autosearch() -> None:
    from app.worker.hh_client import trigger_hh_job

    logger.info("HH autosearch tick")
    await trigger_hh_job("autosearch", timeout=3600.0)


async def run_hh_auto_reject() -> None:
    from app.worker.hh_client import trigger_hh_job

    logger.info("HH auto-reject tick")
    await trigger_hh_job("auto-reject", timeout=600.0)


async def run_hh_token_keepalive() -> None:
    from app.worker.hh_client import trigger_hh_job

    logger.info("HH token keepalive tick")
    await trigger_hh_job("token-keepalive", timeout=60.0)


async def run_ai_eval_relay() -> dict:
    stats = {"published": 0, "consumed": 0, "skipped_reason": None}
    if not AI_EVAL_RELAY_ENABLED:
        stats["skipped_reason"] = "disabled"
        return stats
    if not RABBITMQ_URL:
        stats["skipped_reason"] = "no_rabbitmq"
        return stats

    from app.ai_eval.service import (
        EVENT_REQUEST,
        apply_evaluation_result,
        list_pending_outbox,
        mark_outbox_failed,
        mark_outbox_published,
    )
    from app.messaging.rabbitmq import PermanentHandlerError, drain_queue, publish_json

    async with DistributedLock("hr_ai_eval_relay", ttl=50) as acquired:
        if not acquired:
            stats["skipped_reason"] = "lock"
            return stats
        async with AsyncSessionLocal() as db:
            pending = await list_pending_outbox(db, limit=25, event_type=EVENT_REQUEST)
            for row in pending:
                try:
                    publish_json(
                        rabbit_url=RABBITMQ_URL,
                        queue_name=RABBITMQ_QUEUE_CANDIDATE_EVALUATE_REQUEST,
                        payload=row.payload if isinstance(row.payload, dict) else {},
                        event_type=row.event_type,
                    )
                    await mark_outbox_published(row)
                    stats["published"] += 1
                except Exception as exc:
                    await mark_outbox_failed(row, str(exc))
                    logger.warning("AI eval outbox publish failed id=%s: %s", row.id, exc)
            await db.commit()

        def _handle(payload: dict) -> None:
            async def _apply():
                engine = create_async_engine(
                    DATABASE_URL,
                    poolclass=NullPool,
                    connect_args={"server_settings": {"search_path": DB_SCHEMA}},
                )
                try:
                    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                        ok = await apply_evaluation_result(session, payload)
                        if not ok:
                            raise PermanentHandlerError("evaluation row not found")
                finally:
                    await engine.dispose()

            asyncio.run(_apply())

        stats["consumed"] = await asyncio.to_thread(
            drain_queue,
            rabbit_url=RABBITMQ_URL,
            queue_name=RABBITMQ_QUEUE_CANDIDATE_EVALUATE_RESULT,
            handler=_handle,
            limit=25,
        )
    if stats["published"] or stats["consumed"]:
        logger.info("AI eval relay %s", stats)
    return stats


async def run_interview_reminder_dispatch() -> int:
    async with DistributedLock("interview_reminders_dispatch", ttl=50) as acquired:
        if not acquired:
            logger.info("interview reminders dispatch skipped — another worker holds the lock")
            return 0
        from app.services.interview_reminders import dispatch_due_interview_reminders

        async with AsyncSessionLocal() as db:
            sent = await dispatch_due_interview_reminders(db)
            if sent:
                logger.info("interview reminders sent: %s", sent)
            return sent


async def run_interview_reminder_purge() -> int:
    async with DistributedLock("interview_reminders_purge", ttl=50) as acquired:
        if not acquired:
            logger.info("interview reminders purge skipped — another worker holds the lock")
            return 0
        from app.services.interview_reminders import purge_sent_interview_reminders

        async with AsyncSessionLocal() as db:
            deleted = await purge_sent_interview_reminders(db)
            if deleted:
                logger.info("interview reminders purged: %s", deleted)
            return deleted


async def run_adaptation_notification_tick() -> dict[str, int]:
    async with DistributedLock("adaptation_notifications_tick", ttl=50) as acquired:
        if not acquired:
            return {"sent": 0, "failed": 0, "cancelled": 0}
        from app.adaptation.notifications import run_notification_tick

        async with AsyncSessionLocal() as db:
            result = await run_notification_tick(db)
            if any(result.values()):
                logger.info("adaptation notification tick: %s", result)
            return result
