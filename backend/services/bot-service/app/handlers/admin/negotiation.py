from aiogram.types import Message, CallbackQuery, InputMediaPhoto, FSInputFile
from aiogram.filters import CommandStart, CommandObject
from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext

from app.config import ERROR_MESSAGE, NO_NEGOTIATIONS_MORE, ARCHIVE_CANDIDATE_TEXT, BLACKLIST_CANDIDATE_TEXT, SCHEDULE_APPOINTMENT
from app.filters.roles import IsUser 
from app.app_logging import logger
from app.keyboards.admin.hr import (
    handle_candidate_kb, hr_back_to_menu_kb, pick_up_vacancy_kb
)
from app.keyboards.candidate.candidate import back_to_menu_after_test, pick_up_appointment_day_kb, first_agree_change_vacancy_kb
from app.loader import negotiation_manager, client
from app.utils.text_splitter import split_message


router = Router()


@router.callback_query(IsUser(is_hr=True), F.data == 'negotiations')
async def get_next_negotiation_handler(call: CallbackQuery):
    candidate_id = await negotiation_manager.get_next()
    if candidate_id is None:
        keyboard = hr_back_to_menu_kb()
        await call.message.edit_text(text=NO_NEGOTIATIONS_MORE, reply_markup=keyboard.as_markup())

    info = await client.get(f'/candidate/{candidate_id}/info/html')
    if not info:
        await call.message.answer(ERROR_MESSAGE)
        return
    html = info['text']
    keyboard = await handle_candidate_kb(candidate_id)

    parts = split_message(html)
    # если сообщение помещается — просто edit_text
    if len(parts) == 1:
        await call.message.edit_text(text=parts[0], reply_markup=keyboard.as_markup(), parse_mode='HTML')
    else:
        # первое редактируем, остальные отправляем следом
        await call.message.edit_text(text=parts[0], parse_mode='HTML')
        for part in parts[1:]:
            await call.message.answer(part, parse_mode='HTML')
        await call.message.answer('⬆️ Сообщение было разделено из-за длины', reply_markup=keyboard.as_markup())


@router.callback_query(IsUser(is_hr=True), F.data.startswith('schedule_appointment_id:'))
async def schedule_appointment_handler(call: CallbackQuery, bot: Bot):
    candidate_id = int(call.data.split('schedule_appointment_id:')[1])

    user = await client.get(f'/candidate/{candidate_id}/telegram')
    if not user:
        await call.message.edit_text(text=ERROR_MESSAGE, reply_markup=hr_back_to_menu_kb().as_markup())
    await bot.send_message(chat_id=user['telegram_id'], text=SCHEDULE_APPOINTMENT, reply_markup = await pick_up_appointment_day_kb())

    await call.message.edit_text(text='✅ Успешно')

    await negotiation_manager.read(candidate_id)

    candidate_id = await negotiation_manager.get_next()
    if not candidate_id:
        keyboard = hr_back_to_menu_kb()
        await call.message.edit_text(text=NO_NEGOTIATIONS_MORE, reply_markup=keyboard.as_markup())
        return

    info = await client.get(f'/candidate/{candidate_id}/info/html')
    if not info:
        await call.message.answer(ERROR_MESSAGE)
        return
    html = info['text']
    keyboard = await handle_candidate_kb(candidate_id)

    parts = split_message(html)
    # если сообщение помещается — просто edit_text
    if len(parts) == 1:
        await call.message.edit_text(text=parts[0], reply_markup=keyboard.as_markup(), parse_mode='HTML')
    else:
        # первое редактируем, остальные отправляем следом
        await call.message.edit_text(text=parts[0], parse_mode='HTML')
        for part in parts[1:]:
            await call.message.answer(part, parse_mode='HTML')
        await call.message.answer('⬆️ Сообщение было разделено из-за длины', reply_markup=keyboard.as_markup())




@router.callback_query(IsUser(is_hr=True), F.data.startswith('archieve_id:'))
async def archieve_handler(call: CallbackQuery, bot: Bot):
    candidate_id = int(call.data.split('archieve_id:')[1])

    await negotiation_manager.read(candidate_id)
    result = await client.put(f'/candidate/{candidate_id}/archive')
    if not result:
        await call.message.edit_text(text=ERROR_MESSAGE, reply_markup=hr_back_to_menu_kb().as_markup())
        return

    user = await client.get(f'/candidate/{candidate_id}/telegram')
    if not user:
        await call.message.edit_text(text=ERROR_MESSAGE, reply_markup=hr_back_to_menu_kb().as_markup())
        return

    await bot.send_message(chat_id=user['telegram_id'], text=ARCHIVE_CANDIDATE_TEXT, reply_markup=back_to_menu_after_test.as_markup())

    await call.message.edit_text(text='✅ Успешно')

    candidate_id = await negotiation_manager.get_next()
    if not candidate_id:
        keyboard = hr_back_to_menu_kb()
        await call.message.edit_text(text=NO_NEGOTIATIONS_MORE, reply_markup=keyboard.as_markup())
        return

    info = await client.get(f'/candidate/{candidate_id}/info/html')
    if not info:
        await call.message.answer(ERROR_MESSAGE)
        return
    html = info['text']
    keyboard = await handle_candidate_kb(candidate_id)

    parts = split_message(html)
    # если сообщение помещается — просто edit_text
    if len(parts) == 1:
        await call.message.edit_text(text=parts[0], reply_markup=keyboard.as_markup(), parse_mode='HTML')
    else:
        # первое редактируем, остальные отправляем следом
        await call.message.edit_text(text=parts[0], parse_mode='HTML')
        for part in parts[1:]:
            await call.message.answer(part, parse_mode='HTML')
        await call.message.answer('⬆️ Сообщение было разделено из-за длины', reply_markup=keyboard.as_markup())
    


@router.callback_query(IsUser(is_hr=True), F.data.startswith('blacklist_id:'))
async def blacklist_handler(call: CallbackQuery, bot: Bot):
    candidate_id = int(call.data.split('blacklist_id:')[1])

    await negotiation_manager.read(candidate_id)
    result = await client.put(f'/candidate/{candidate_id}/blacklist')
    if not result:
        await call.message.edit_text(text=ERROR_MESSAGE, reply_markup=hr_back_to_menu_kb().as_markup())
        return

    user = await client.get(f'/candidate/{candidate_id}/telegram')
    if not user:
        await call.message.edit_text(text=ERROR_MESSAGE, reply_markup=hr_back_to_menu_kb().as_markup())
        return

    await bot.send_message(chat_id=user['telegram_id'], text=BLACKLIST_CANDIDATE_TEXT, reply_markup=back_to_menu_after_test.as_markup())

    await call.message.edit_text(text='✅ Успешно')


    candidate_id = await negotiation_manager.get_next()
    if not candidate_id:
        keyboard = hr_back_to_menu_kb()
        await call.message.edit_text(text=NO_NEGOTIATIONS_MORE, reply_markup=keyboard.as_markup())
        return

    info = await client.get(f'/candidate/{candidate_id}/info/html')
    if not info:
        await call.message.answer(ERROR_MESSAGE)
        return
    html = info['text']
    keyboard = await handle_candidate_kb(candidate_id)

    parts = split_message(html)
    # если сообщение помещается — просто edit_text
    if len(parts) == 1:
        await call.message.edit_text(text=parts[0], reply_markup=keyboard.as_markup(), parse_mode='HTML')
    else:
        # первое редактируем, остальные отправляем следом
        await call.message.edit_text(text=parts[0], parse_mode='HTML')
        for part in parts[1:]:
            await call.message.answer(part, parse_mode='HTML')
        await call.message.answer('⬆️ Сообщение было разделено из-за длины', reply_markup=keyboard.as_markup())



@router.callback_query(IsUser(is_hr=True), F.data.startswith('change_vacancy_id:'))
async def change_vacancy_handler(call: CallbackQuery, bot: Bot):
    candidate_id = int(call.data.split('change_vacancy_id:')[1])

    keyboard = await pick_up_vacancy_kb(candidate_id)
    if not keyboard:
        await call.message.edit_text(text=ERROR_MESSAGE, reply_markup=hr_back_to_menu_kb().as_markup())
        return
    await call.message.edit_text(text='Выберите вакансию:', reply_markup=keyboard.as_markup())
    

@router.callback_query(IsUser(is_hr=True), F.data.startswith('vacancy-id:'))
async def pick_up_vacancy_handler(call: CallbackQuery, bot: Bot):
    vacancy, candidate = call.data.split('_')
    vacancy_id = int(vacancy.split('vacancy-id:')[1])
    candidate_id = int(candidate.split('candidate-id:')[1])
    result = await client.post(
        '/candidate/vacancy/change',
        json={
            "candidate_id": candidate_id,
            "vacancy_id": vacancy_id
        }
    )
    if not result:
        await call.message.edit_text(text=ERROR_MESSAGE, reply_markup=hr_back_to_menu_kb().as_markup())
        return
    
    user = await client.get(f'/candidate/{candidate_id}/telegram')
    if not user:
        await call.message.edit_text(text=ERROR_MESSAGE, reply_markup=hr_back_to_menu_kb().as_markup())
        return
    
    vacancy_desc = await client.get(f"/vacancy/{vacancy_id}/description")
    if not vacancy_desc:
        await call.message.edit_text(text=ERROR_MESSAGE, reply_markup=hr_back_to_menu_kb().as_markup())
        return
    
    text = 'Для вас есть новая вакансия:\n\n' + vacancy_desc
    
    await bot.send_message(chat_id=user['telegram_id'], text=text, reply_markup=first_agree_change_vacancy_kb())

    await call.message.edit_text(text='✅ Успешно')

    await negotiation_manager.read(candidate_id)

    candidate_id = await negotiation_manager.get_next()
    if not candidate_id:
        keyboard = hr_back_to_menu_kb()
        await call.message.edit_text(text=NO_NEGOTIATIONS_MORE, reply_markup=keyboard.as_markup())
        return

    info = await client.get(f'/candidate/{candidate_id}/info/html')
    if not info:
        await call.message.answer(ERROR_MESSAGE)
        return
    html = info['text']
    keyboard = await handle_candidate_kb(candidate_id)

    parts = split_message(html)
    # если сообщение помещается — просто edit_text
    if len(parts) == 1:
        await call.message.edit_text(text=parts[0], reply_markup=keyboard.as_markup(), parse_mode='HTML')
    else:
        # первое редактируем, остальные отправляем следом
        await call.message.edit_text(text=parts[0], parse_mode='HTML')
        for part in parts[1:]:
            await call.message.answer(part, parse_mode='HTML')
        await call.message.answer('⬆️ Сообщение было разделено из-за длины', reply_markup=keyboard.as_markup())