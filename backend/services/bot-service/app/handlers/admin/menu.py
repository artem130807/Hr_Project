from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, CommandObject
from aiogram import F, Router
from aiogram.fsm.context import FSMContext

from app.config import WELCOME_CANDIDATE_TEXT, WELCOME_ADMIN_TEXT, ERROR_MESSAGE
from app.filters.roles import IsUser 
from app.keyboards.admin.hr import (
    hr_main_menu
)


router = Router()


@router.callback_query(IsUser(is_hr=True), F.data == 'back_to_hr_main_menu')
async def hr_main_menu_handler(call: CallbackQuery, state: FSMContext):
    await call.answer()
    text = WELCOME_ADMIN_TEXT.format(telegram_id=call.from_user.id)
    keyboard = await hr_main_menu()
    await call.message.answer(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')



@router.message(IsUser(is_hr=True), CommandStart())
async def start_for_hr(message: Message):
    kb = await hr_main_menu()
    if kb is None:
        await message.answer(text=ERROR_MESSAGE)
        return

    await message.answer(
        text=WELCOME_ADMIN_TEXT.format(telegram_id=message.from_user.id),
        reply_markup=kb.as_markup(),
        parse_mode='HTML',
    )