from datetime import datetime, timezone

from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, CommandObject
from aiogram import F, Router
from aiogram.fsm.context import FSMContext

from app.config import HR_CONTACT, WELCOME_CANDIDATE_TEXT, WELCOME_ADMIN_TEXT, AGREEMENT_TEXT, ERROR_MESSAGE
from app.loader import client
from app.loader import redis_client as redis
from app.api.endpoints import Endpoints
from app.api import schemas
from app.filters.candidate_test import OnTestFilter
from app.keyboards.admin.hr import hr_main_menu
from app.keyboards.candidate.candidate import agreement_kb
from app.media.video_loader import get_office_video, cache_office_video_file_id
from app.app_logging import logger

router = Router()


@router.message(OnTestFilter(False),CommandStart())
async def start_for_new_user(message: Message, command: CommandObject, state: FSMContext):
    token = command.args
    if token:
        token_data = await client.get(Endpoints.get_invite_token, token=token)
        if token_data is None:
            await message.answer('Ваша пригласительная ссылка недействительна, запросите новую.')
            return
        expires_at = datetime.fromisoformat(token_data['expires_at'].replace('Z', '+00:00'))
        current_time = datetime.now(timezone.utc)
        if expires_at < current_time:
            await message.answer('Истек срок действия пригласительной ссылки в бот, запросите новую.')
            return
        role = token_data['role']
        id = token_data['entity_id']
        logger.info(f"\n\nENTITY_ID = {id}")
    else:
        await message.answer(f'Это бот Hr платформы.\nЕсли нужна помощь с откликом — свяжитесь с {HR_CONTACT}')
        return
    
    bot_user = schemas.BotUserCreate(
        telegram_id=str(message.from_user.id),
        name=message.from_user.full_name,
        role=role
    )
    user = await client.post(Endpoints.post_user, json=bot_user.model_dump())
    if not user:
        await message.answer(ERROR_MESSAGE)
        return
    
    url = None
    if role in ['owner', 'hr', 'lead', 'art', 'dev']:
        url = f'/admin/user/{id}'
    elif role=='candidate':
        url = f'/candidate/{id}'

    await client.patch(
            url,
            json={
                "user_id": user['id']
            }
        )    
        
    if role not in ['candidate', 'employee']:
        text = WELCOME_ADMIN_TEXT.format(telegram_id = message.from_user.id)
        keyboard = await hr_main_menu()
        if not keyboard:
            await message.answer(text=ERROR_MESSAGE)
            return
    elif role == 'candidate':
        status = "откликнулся"
        status_uodated = await client.put(f'/candidate/{id}/status', json={"status": status})
        logger.info(f"Status {status} updated: {status_uodated}")
        text = AGREEMENT_TEXT
        keyboard = agreement_kb
    await state.update_data(agreement=True)

    if role == 'candidate':
        from aiogram.exceptions import TelegramRetryAfter
        import asyncio
        video = await get_office_video(redis)
        try:
            sent_video = await message.answer_video(video=video)
        except Exception as e:
            if isinstance(e, TelegramRetryAfter):
                await asyncio.sleep(e.retry_after)
                sent_video = await message.answer_video(video=video)
            else:
                logger.error(f"Failed to send office video: {e}")
                sent_video = None
        if sent_video and isinstance(video, FSInputFile):
            await cache_office_video_file_id(redis, sent_video)

    await message.answer(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
