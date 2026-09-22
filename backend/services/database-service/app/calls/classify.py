"""Classify pending CallConversation rows via WhisperAi."""
from __future__ import annotations

import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.app_logging import logger
from app.calls.openai_client import WhisperAiClient, WhisperAiError
from app.calls.phones import conversation_involves_allowed_phones
from app.calls.whisper import build_user_prompt, heuristic_without_transcript
from app.config import (
    CALL_WHISPER_BATCH_SIZE,
    CALL_WHISPER_EMPTY_AS_DROPPED_SECONDS,
    CALL_WHISPER_MAX_TRANSCRIPT_CHARS,
    CALL_WHISPER_REQUEST_DELAY_SECONDS,
    OPENAI_API_TOKEN,
)
from app.repositories.call_conversation_repository import CallConversationRepository
from app.t2.mapping import transcript_from_payload


async def classify_pending_conversations(
    db: AsyncSession,
    *,
    client: Optional[WhisperAiClient] = None,
    batch_size: Optional[int] = None,
    delay_seconds: Optional[float] = None,
) -> dict:
    stats = {
        "fetched": 0,
        "classified": 0,
        "heuristic": 0,
        "skipped": 0,
        "skipped_phone": 0,
        "waiting_stt": 0,
        "errors": 0,
    }
    repo = CallConversationRepository(db)
    limit = batch_size if batch_size is not None else CALL_WHISPER_BATCH_SIZE
    pause = delay_seconds if delay_seconds is not None else CALL_WHISPER_REQUEST_DELAY_SECONDS
    rows = list(await repo.list_pending(limit=limit))
    stats["fetched"] = len(rows)
    if not rows:
        return stats

    own_client = client is None
    if own_client:
        if not OPENAI_API_TOKEN:
            logger.warning("WhisperAi: OPENAI_API_TOKEN is empty — only local drop heuristics")
            stats["skipped_reason"] = "no_token"
            # still apply local heuristics without the API
        else:
            try:
                client = WhisperAiClient()
            except WhisperAiError as exc:
                logger.warning("WhisperAi client init failed: %s", exc)
                stats["skipped_reason"] = "no_token"
                stats["errors"] += 1
                client = None

    for index, row in enumerate(rows):
        used_api = False
        try:
            if not conversation_involves_allowed_phones(row):
                stats["skipped_phone"] += 1
                continue
            outcome = heuristic_without_transcript(
                row, empty_as_dropped_seconds=CALL_WHISPER_EMPTY_AS_DROPPED_SECONDS
            )
            if outcome is None:
                words = transcript_from_payload(getattr(row, "payload", None))
                if not words:
                    stats["waiting_stt"] += 1
                    continue
                if client is None:
                    stats["skipped"] += 1
                    continue
                prompt = build_user_prompt(row, max_chars=CALL_WHISPER_MAX_TRANSCRIPT_CHARS)
                outcome = await client.classify(prompt)
                used_api = True
            else:
                stats["heuristic"] += 1

            applied = await repo.apply_whisper_result(
                row.id,
                status=outcome["status"],
                description=outcome["description"],
            )
            if applied:
                stats["classified"] += 1
            else:
                stats["skipped"] += 1
        except WhisperAiError as exc:
            stats["errors"] += 1
            logger.warning("WhisperAi failed for call %s: %s", getattr(row, "id", None), exc)
            if exc.status_code == 429:
                logger.warning("WhisperAi rate-limited — stopping this tick")
                break
        except Exception:
            stats["errors"] += 1
            logger.exception("WhisperAi unexpected error for call %s", getattr(row, "id", None))

        if pause and index < len(rows) - 1 and used_api:
            await asyncio.sleep(pause)

    logger.info("WhisperAi classify finished: %s", stats)
    return stats
