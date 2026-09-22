import asyncio

from fastapi import APIRouter, Depends, HTTPException
from aiogram import Bot
from aiogram.types import Message

from app.middleware import get_bot
from app.dependencies import get_db_client
from app.api.db_client import APIClient
from app.keyboards.candidate.candidate import first_agree_change_vacancy_kb, offer_kb
from app.app_logging import logger
from app.api.endpoints import Endpoints


router = APIRouter()


@router.post('/candidate/new-vacancy')
async def send_new_vacancy_endpoint(
    user_id: int,
    vacancy_id: int,
    bot: Bot = Depends(get_bot),
    db: APIClient = Depends(get_db_client)
):
    try:
        vacancy_desc = await db.get(f"/vacancy/{vacancy_id}/description")
        if not vacancy_desc:
            raise HTTPException(404, 'Vacancy description not found')
        
        text = 'Для вас есть новая вакансия:\n\n' + vacancy_desc
        
        await bot.send_message(chat_id=user_id, text=text, reply_markup=first_agree_change_vacancy_kb())

        return {"ok": True}
    
    except Exception as e:
        logger.error(f'Error sending new vacancy: {str(e)}')
        raise HTTPException(500, f'Error sending new vacancy: {str(e)}')




@router.post('/candidate/send-offer')
async def send_offer_endpoint(
    offer_text: str,
    user_id: int,
    bot: Bot = Depends(get_bot),
    db: APIClient = Depends(get_db_client)
):
    try:
        await bot.send_message(chat_id=user_id, text=offer_text)
        await bot.send_message(chat_id=user_id, text="Принять оффер:", reply_markup=offer_kb())
        return {"ok": True}
    except Exception as e:
        logger.error(f'Error sending offer: {str(e)}')
        raise HTTPException(500, f'Error sending offer: {str(e)}')



@router.post('/candidate/exercise')
async def start_exercise_endpoint(
    user_id: int,
    instruction_text: str,
    minutes: int,
    bot: Bot = Depends(get_bot),
    db: APIClient = Depends(get_db_client)
):
    try:
        # Отправляем инструкцию сразу
        await bot.send_message(chat_id=user_id, text=instruction_text)

        # Запускаем таймер в фоне
        asyncio.create_task(run_timer(bot, db, user_id, minutes))

        return {"ok": True}
    except Exception as e:
        logger.error(f'Error creating task for exercise timer: {str(e)}')
        raise HTTPException(500, f'Error creating task for exercise timer: {str(e)}')


async def run_timer(bot: Bot, db: APIClient, user_id: int, minutes: int):
    text = "🕓 Осталось {min} мин."
    message = await bot.send_message(chat_id=user_id, text=text.format(min=minutes))

    for mins_left in range(minutes - 1, -1, -1):
        await asyncio.sleep(60)
        try:
            if mins_left > 0:
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message.message_id,
                    text=text.format(min=mins_left)
                )
            else:
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message.message_id,
                    text="✅ Время вышло!"
                )
                candidate = await db.get(Endpoints.get_candidate_by_telegram_id, telegram_id = user_id)
                if candidate:
                    candidate_id = candidate['id']
                    status = "собес"
                    status_uodated = await db.put(f'/candidate/{candidate_id}/status', json={"status": status})
                    logger.info(f"Status {status} updated: {status_uodated}")
        except Exception:
            break  # сообщение могли удалить





