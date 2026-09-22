"""Pull T2 ATS recordings + STT into CallConversation rows."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.app_logging import logger
from app.config import (
    T2_ATS_BASE,
    T2_CALL_SYNC_LOOKBACK_HOURS,
    T2_CALL_SYNC_MAX_RECORDS_PER_TICK,
    T2_CALL_SYNC_MAX_PAGES,
    T2_CALL_SYNC_PAGE_SIZE,
    T2_STT_BACKFILL_BATCH_SIZE,
    T2_STT_BACKFILL_MAX_AGE_DAYS,
    T2_STT_BACKFILL_REQUEST_DELAY_SECONDS,
    T2_STT_BACKFILL_SCAN_MULTIPLIER,
)
from app.repositories.call_conversation_repository import CallConversationRepository
from app.repositories.t2_oauth_token_repository import T2OAuthTokenRepository
from app.t2.auth import ensure_access_token
from app.t2.client import T2AtsClient, T2AtsError
from app.t2.mapping import normalize_call_record, transcript_from_payload
from app.t2.tokens import T2TokenError, access_token_of as load_access_token


async def sync_call_conversations(
    db: AsyncSession,
    *,
    client: Optional[T2AtsClient] = None,
    lookback_hours: Optional[int] = None,
    now: Optional[datetime] = None,
) -> dict:
    """Fetch recorded calls and transcripts; upsert into call_conversations."""
    stats = {
        "fetched": 0,
        "upserted": 0,
        "skipped": 0,
        "skipped_existing": 0,
        "deferred_to_backfill": 0,
        "stt_missing": 0,
        "errors": 0,
    }
    own_client = client is None
    token_repo = T2OAuthTokenRepository(db)
    if own_client:
        if not T2_ATS_BASE:
            logger.warning("T2 call sync skipped — T2_ATS_BASE is empty")
            stats["skipped_reason"] = "no_base"
            return stats
        try:
            access_token = await ensure_access_token(token_repo)
        except T2TokenError as exc:
            logger.warning("T2 call sync skipped — token refresh failed: %s", exc)
            stats["skipped_reason"] = "refresh_failed"
            stats["errors"] += 1
            return stats
        if not access_token:
            logger.info("T2 call sync skipped — no OAuth access_token in t2_oauth_tokens")
            stats["skipped_reason"] = "no_token"
            return stats
        client = T2AtsClient(access_token=access_token)

    end = now or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    hours = lookback_hours if lookback_hours is not None else T2_CALL_SYNC_LOOKBACK_HOURS
    start = end - timedelta(hours=hours)

    repo = CallConversationRepository(db)
    records: list[dict] = []
    refreshed_after_403 = False
    max_records = max(1, int(T2_CALL_SYNC_MAX_RECORDS_PER_TICK or 1))
    for page in range(T2_CALL_SYNC_MAX_PAGES):
        try:
            chunk = await client.list_call_records(
                start=start,
                end=end,
                page=page,
                size=T2_CALL_SYNC_PAGE_SIZE,
                is_recorded=True,
            )
        except T2AtsError as exc:
            if (
                own_client
                and not refreshed_after_403
                and exc.status_code in (401, 403)
            ):
                logger.warning("T2 call-records unauthorized — forcing token refresh")
                try:
                    access_token = await ensure_access_token(token_repo, force=True)
                except T2TokenError as refresh_exc:
                    logger.warning("T2 token refresh after 403 failed: %s", refresh_exc)
                    stats["errors"] += 1
                    break
                if not access_token:
                    stats["errors"] += 1
                    break
                client.access_token = access_token
                refreshed_after_403 = True
                continue
            logger.warning("T2 call-records page %s failed: %s", page, exc)
            stats["errors"] += 1
            break
        if not chunk:
            break
        records.extend(chunk)
        if len(records) >= max_records:
            records = records[:max_records]
            stats["limited_by_cap"] = True
            break
        if len(chunk) < T2_CALL_SYNC_PAGE_SIZE:
            break

    stats["fetched"] = len(records)
    normalized: list[dict] = []
    seen_filenames: set[str] = set()
    for raw in records:
        mapped = normalize_call_record(raw)
        if mapped is None:
            stats["skipped"] += 1
            continue
        filename = mapped["filename"]
        if filename in seen_filenames:
            stats["skipped"] += 1
            continue
        seen_filenames.add(filename)
        normalized.append(mapped)

    existing_by_filename: dict = {}
    if hasattr(repo, "get_existing_by_filenames"):
        existing_by_filename = await repo.get_existing_by_filenames(
            [item["filename"] for item in normalized]
        )

    for mapped in normalized:
        filename = mapped["filename"]
        existing = existing_by_filename.get(filename)
        if existing is not None:
            stats["skipped_existing"] += 1
            if not transcript_from_payload(getattr(existing, "payload", None)):
                stats["deferred_to_backfill"] += 1
            continue
        try:
            words = await client.get_transcript(filename)
        except T2AtsError as exc:
            logger.warning("T2 STT failed for %s: %s", filename, exc)
            words = []
            stats["errors"] += 1
        if not words:
            stats["stt_missing"] += 1
        try:
            await repo.upsert_from_ats(mapped, words)
            stats["upserted"] += 1
        except Exception:
            logger.exception("Failed to persist CallConversation %s", filename)
            stats["errors"] += 1

    logger.info("T2 call sync finished: %s", stats)
    return stats


async def backfill_missing_transcripts(
    db: AsyncSession,
    *,
    client: Optional[T2AtsClient] = None,
    batch_size: Optional[int] = None,
    request_delay_seconds: Optional[float] = None,
    scan_multiplier: Optional[int] = None,
) -> dict:
    """Retry STT for saved calls with empty transcript."""
    stats = {
        "scanned": 0,
        "updated": 0,
        "stt_missing": 0,
        "skipped_old": 0,
        "errors": 0,
    }
    own_client = client is None
    token_repo = T2OAuthTokenRepository(db)
    if own_client:
        if not T2_ATS_BASE:
            logger.warning("T2 STT backfill skipped — T2_ATS_BASE is empty")
            stats["skipped_reason"] = "no_base"
            return stats
        try:
            access_token = await ensure_access_token(token_repo)
        except T2TokenError as exc:
            logger.warning("T2 STT backfill skipped — token refresh failed: %s", exc)
            stats["skipped_reason"] = "refresh_failed"
            stats["errors"] += 1
            return stats
        if not access_token:
            logger.info("T2 STT backfill skipped — no OAuth access_token in t2_oauth_tokens")
            stats["skipped_reason"] = "no_token"
            return stats
        client = T2AtsClient(access_token=access_token)

    limit = batch_size if batch_size is not None else T2_STT_BACKFILL_BATCH_SIZE
    delay = (
        request_delay_seconds
        if request_delay_seconds is not None
        else T2_STT_BACKFILL_REQUEST_DELAY_SECONDS
    )
    scan = scan_multiplier if scan_multiplier is not None else T2_STT_BACKFILL_SCAN_MULTIPLIER
    now = datetime.now(timezone.utc)
    min_call_start_time = now - timedelta(days=T2_STT_BACKFILL_MAX_AGE_DAYS)
    repo = CallConversationRepository(db)
    rows, skipped_old = await repo.list_missing_transcript_for_backfill(
        limit=limit,
        scan_multiplier=scan,
        min_call_start_time=min_call_start_time,
    )
    rows = list(rows)
    stats["skipped_old"] = int(skipped_old or 0)
    stats["scanned"] = len(rows)
    refreshed_after_403 = False

    for index, row in enumerate(rows):
        filename = str(getattr(row, "filename", "") or "").strip()
        if not filename:
            continue
        try:
            words = await client.get_transcript(filename)
        except T2AtsError as exc:
            if own_client and not refreshed_after_403 and exc.status_code in (401, 403):
                logger.warning("T2 STT unauthorized — forcing token refresh")
                try:
                    access_token = await ensure_access_token(token_repo, force=True)
                except T2TokenError as refresh_exc:
                    logger.warning("T2 token refresh during STT backfill failed: %s", refresh_exc)
                    stats["errors"] += 1
                    break
                if not access_token:
                    stats["errors"] += 1
                    break
                client.access_token = access_token
                refreshed_after_403 = True
                try:
                    words = await client.get_transcript(filename)
                except T2AtsError as retry_exc:
                    logger.warning("T2 STT retry failed for %s: %s", filename, retry_exc)
                    stats["errors"] += 1
                    continue
            else:
                logger.warning("T2 STT backfill failed for %s: %s", filename, exc)
                stats["errors"] += 1
                continue
        if not words:
            stats["stt_missing"] += 1
        else:
            updated = await repo.update_transcript(row.id, words)
            if updated:
                stats["updated"] += 1
        if delay and index < len(rows) - 1:
            await asyncio.sleep(delay)

    logger.info("T2 STT backfill finished: %s", stats)
    return stats
