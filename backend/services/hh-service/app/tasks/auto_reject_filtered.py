"""
Background job: for each published vacancy with a VacancyFilter,
load unviewed HH responses and discard those that fail the filter.

Rate limit: a short tick (default every 10 minutes) sends at most
AUTO_REJECT_BATCH_SIZE discards (default 5) and scans at most
AUTO_REJECT_MAX_CHECKED resumes, with a pause between HH writes.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import HTTPException

import app.config as conf
from app.clients.db_client import APICLient
from app.clients.hh.simple_hh_client import SimpleHHClient
from app.app_logging import logger
from app.utils.vacancy_filter_match import (
    is_unviewed_negotiation,
    matches_vacancy_filter,
    resolve_hh_filter_action,
    resume_has_filter_fields,
)

DEFAULT_DISCARD_MESSAGE = (
    "Спасибо за отклик! К сожалению, ваш профиль не подходит под требования этой вакансии."
)


async def _rotate_start_index(n: int) -> int:
    """Fair round-robin across vacancies so the first listing does not starve the rest."""
    if n <= 1:
        return 0
    try:
        from app.scheduler.lock import redis

        raw = await redis.incr(conf.AUTO_REJECT_RR_KEY)
        return (int(raw) - 1) % n
    except Exception as e:
        logger.warning("auto_reject round-robin cursor unavailable: %s", e)
        return 0


async def _resolve_resume(hh: SimpleHHClient, item: dict) -> Optional[dict]:
    embedded = item.get("resume")
    if resume_has_filter_fields(embedded):
        return embedded
    resume_id = None
    if isinstance(embedded, dict):
        resume_id = embedded.get("id")
    if not resume_id:
        return embedded if isinstance(embedded, dict) else None
    try:
        return await hh.get_resume(str(resume_id))
    except Exception as e:
        logger.warning("Failed to load resume %s: %s", resume_id, e)
        return embedded if isinstance(embedded, dict) else None


async def _iter_response_collection(
    hh: SimpleHHClient,
    hh_vacancy_id: str,
    *,
    per_page: int = 50,
):
    meta = await hh.get_negotiations_meta(str(hh_vacancy_id))
    if not isinstance(meta, dict):
        return
    collections = meta.get("collections") or []
    coll = next(
        (c for c in collections if isinstance(c, dict) and c.get("id") == "response"),
        None,
    )
    if not coll or not coll.get("url"):
        logger.info("No 'response' collection for hh vacancy %s", hh_vacancy_id)
        return

    page = 0
    while True:
        page_data = await hh.list_negotiations_collection(
            coll["url"], page=page, per_page=per_page
        )
        if not isinstance(page_data, dict):
            break
        items = page_data.get("items") or []
        for item in items:
            if isinstance(item, dict):
                yield item
        pages = int(page_data.get("pages") or 1)
        if page >= pages - 1 or not items:
            break
        page += 1
        await asyncio.sleep(0.3)


async def process_vacancy_responses(
    hh: SimpleHHClient,
    vacancy: dict,
    vacancy_filter: dict,
    *,
    discard_message: str,
    include_viewed: bool = False,
    max_rejects: Optional[int] = None,
    max_checked: Optional[int] = None,
    discard_delay: float = 0.0,
) -> dict[str, int]:
    stats = {
        "checked": 0,
        "matched": 0,
        "rejected": 0,
        "considered": 0,
        "errors": 0,
        "skipped_viewed": 0,
        "capped": 0,
    }
    hh_vacancy_id = vacancy.get("hh_vacancy_id")
    if not hh_vacancy_id:
        return stats

    hh_action = resolve_hh_filter_action(vacancy_filter)

    def _writes() -> int:
        return stats["rejected"] + stats["considered"]

    async for item in _iter_response_collection(hh, str(hh_vacancy_id)):
        if max_rejects is not None and _writes() >= max_rejects:
            stats["capped"] = 1
            break
        if max_checked is not None and stats["checked"] >= max_checked:
            stats["capped"] = 1
            break

        if not include_viewed and not is_unviewed_negotiation(item):
            stats["skipped_viewed"] += 1
            continue

        stats["checked"] += 1
        # Prefer embedded resume so we do not mark the topic viewed before discard
        # (GET resume counts as viewed and can change available HH actions).
        resume = item.get("resume") if isinstance(item.get("resume"), dict) else None
        if not resume_has_filter_fields(resume):
            resume = await _resolve_resume(hh, item)
        matched = matches_vacancy_filter(resume, vacancy_filter)

        if hh_action == "consider":
            if not matched:
                continue
            stats["matched"] += 1
        else:
            if matched:
                stats["matched"] += 1
                continue

        nid = item.get("id")
        if not nid:
            stats["errors"] += 1
            continue
        try:
            if hh_action == "consider":
                await hh.consider_negotiation(str(nid), topic=item)
                stats["considered"] += 1
                logger.info(
                    "Consider negotiation %s for vacancy %s (filter %s)",
                    nid,
                    vacancy.get("id"),
                    vacancy_filter.get("id"),
                )
            else:
                await hh.discard_negotiation(
                    str(nid), message=discard_message, topic=item
                )
                stats["rejected"] += 1
                logger.info(
                    "Rejected negotiation %s for vacancy %s (filter %s)",
                    nid,
                    vacancy.get("id"),
                    vacancy_filter.get("id"),
                )
        except Exception as e:
            stats["errors"] += 1
            logger.error("HH filter action failed for negotiation %s: %s", nid, e)
        if discard_delay > 0:
            await asyncio.sleep(discard_delay)

    return stats


async def auto_reject_filtered(
    db: APICLient,
    hh: SimpleHHClient,
    *,
    discard_message: Optional[str] = None,
    vacancy_id: Optional[int] = None,
    include_viewed: Optional[bool] = None,
    batch_size: Optional[int] = None,
    max_checked: Optional[int] = None,
    discard_delay: Optional[float] = None,
) -> dict[str, Any]:
    """
    Main entry: published vacancies with filter_id + hh_vacancy_id →
    HH «Неразобранные» → discard mismatches.

    Each call sends at most ``batch_size`` refusals (default 5) so HH and
    our workers stay within a gentle budget. The scheduler repeats this
    every AUTO_REJECT_INTERVAL_MINUTES.

    If ``vacancy_id`` is set, only that local vacancy is processed.
    Manual runs (vacancy_id set) include already-viewed responses by default —
    the interval job still skips viewed.
    """
    message = discard_message or DEFAULT_DISCARD_MESSAGE
    limit = batch_size if batch_size is not None else conf.AUTO_REJECT_BATCH_SIZE
    scan_cap = max_checked if max_checked is not None else conf.AUTO_REJECT_MAX_CHECKED
    pause = discard_delay if discard_delay is not None else conf.AUTO_REJECT_DISCARD_DELAY_SEC
    interval = conf.AUTO_REJECT_INTERVAL_MINUTES
    # Manual one-vacancy run: process viewed too (prior get_resume may have marked them).
    if include_viewed is None:
        include_viewed = vacancy_id is not None
    summary: dict[str, Any] = {
        "vacancies_processed": 0,
        "checked": 0,
        "matched": 0,
        "rejected": 0,
        "considered": 0,
        "errors": 0,
        "skipped_viewed": 0,
        "vacancy_id": vacancy_id,
        "include_viewed": include_viewed,
        "error_detail": None,
        "batch_size": limit,
        "max_checked": scan_cap,
        "interval_minutes": interval,
        "batch_capped": False,
    }

    if vacancy_id is not None:
        vacancy = await db.get(f"/vacancy/{vacancy_id}", raise_on_error=True)
        if not isinstance(vacancy, dict):
            raise HTTPException(404, f"Вакансия #{vacancy_id} не найдена")
        if not vacancy.get("hh_vacancy_id"):
            raise HTTPException(
                400,
                "Вакансия не привязана к HH.ru — сначала опубликуйте или импортируйте её",
            )
        if not vacancy.get("filter_id"):
            raise HTTPException(400, "К вакансии не привязан фильтр")
        vacancies = [vacancy]
    else:
        vacancies = await db.get("/vacancies/published")
        if not vacancies:
            logger.info("auto_reject_filtered: no published vacancies")
            return summary
        if not isinstance(vacancies, list):
            logger.warning("auto_reject_filtered: unexpected vacancies payload")
            return summary

    eligible = [
        v
        for v in vacancies
        if isinstance(v, dict) and v.get("hh_vacancy_id") and v.get("filter_id")
    ]
    if vacancy_id is None and len(eligible) > 1:
        start = await _rotate_start_index(len(eligible))
        eligible = eligible[start:] + eligible[:start]

    remaining_rejects = limit
    remaining_checked = scan_cap

    for vacancy in eligible:
        if remaining_rejects <= 0 or remaining_checked <= 0:
            summary["batch_capped"] = True
            break

        filter_id = vacancy["filter_id"]
        try:
            vacancy_filter = await db.get(f"/vacancy-filters/{filter_id}")
        except Exception as e:
            logger.error("Failed to load filter %s: %s", filter_id, e)
            summary["errors"] += 1
            summary["error_detail"] = f"filter load failed: {e}"
            continue
        if not vacancy_filter:
            logger.warning("Filter %s not found for vacancy %s", filter_id, vacancy.get("id"))
            summary["errors"] += 1
            summary["error_detail"] = f"filter #{filter_id} not found"
            continue

        summary["vacancies_processed"] += 1
        try:
            stats = await process_vacancy_responses(
                hh,
                vacancy,
                vacancy_filter,
                discard_message=message,
                include_viewed=include_viewed,
                max_rejects=remaining_rejects,
                max_checked=remaining_checked,
                discard_delay=pause,
            )
        except Exception as e:
            logger.error("Failed processing vacancy %s: %s", vacancy.get("id"), e)
            summary["errors"] += 1
            summary["error_detail"] = str(e)
            continue

        for key in ("checked", "matched", "rejected", "considered", "errors", "skipped_viewed"):
            summary[key] += stats.get(key, 0)
        remaining_rejects -= int(stats.get("rejected") or 0) + int(stats.get("considered") or 0)
        remaining_checked -= int(stats.get("checked") or 0)
        if stats.get("capped"):
            summary["batch_capped"] = True
            break

    if remaining_rejects <= 0 or remaining_checked <= 0:
        summary["batch_capped"] = True

    logger.info("auto_reject_filtered finished: %s", summary)
    return summary
