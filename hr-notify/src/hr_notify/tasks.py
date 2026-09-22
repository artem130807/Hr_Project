"""Send HR notifications to a Telegram chat."""
from __future__ import annotations

import asyncio
import logging
import os

from hr_notify.huey_app import huey

logger = logging.getLogger(__name__)


def resolve_chat_id() -> str:
    return (os.getenv("HR_NOTIFY_CHAT_ID") or os.getenv("CHAT_ID") or "").strip()


@huey.task(name="send_hr_telegram_notification")
def send_hr_telegram_notification(text: str) -> None:
    asyncio.run(_send_telegram(text))


async def _send_telegram(text: str) -> None:
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.enums import ParseMode

    token = (os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not configured")
    chat_id_raw = resolve_chat_id()
    if not chat_id_raw:
        raise RuntimeError("HR_NOTIFY_CHAT_ID / CHAT_ID is not configured")
    try:
        chat_id = int(chat_id_raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid HR notify chat id: {chat_id_raw!r}") from exc

    bot_kwargs = {
        "token": token,
        "default": DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    }
    proxy = (os.getenv("TELEGRAM_PROXY") or "").strip()
    if proxy:
        bot_kwargs["session"] = AiohttpSession(proxy=proxy)
    bot = Bot(**bot_kwargs)
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    finally:
        await bot.session.close()
    logger.info("hr notify sent chat_id=%s", chat_id)


def send_hr_telegram_notification_impl(text: str, *, send_message) -> None:
    send_message(text)
