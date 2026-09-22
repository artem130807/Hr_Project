from datetime import datetime, timezone

from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, CommandObject
from aiogram import F, Router
from aiogram.fsm.context import FSMContext

from app.config import WELCOME_CANDIDATE_TEXT
from app.filters.roles import IsUser 
from app.filters.candidate_test import OnTestFilter
from app.keyboards.candidate.candidate import welcome_menu_kb, agreement_kb
from app.utils.analytic_service import pass_checkpoint
from app.app_logging import logger


router = Router()


@router.message(IsUser(is_candidate=True), OnTestFilter(False), CommandStart())
async def start_for_candidate(message: Message):

    keyboard = await welcome_menu_kb(message.from_user.id)
    await message.answer(text=WELCOME_CANDIDATE_TEXT, reply_markup=keyboard.as_markup())


@router.callback_query(OnTestFilter(False), IsUser(is_candidate=True), F.data == 'main_candidate_menu')
async def candidate_main_menu(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get('agreement'):
        user_id = str(call.from_user.id)
        await pass_checkpoint(user_id, 'agreement')
        await state.clear()
    await call.answer()
    text = WELCOME_CANDIDATE_TEXT
    keyboard = await welcome_menu_kb(call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard.as_markup())


@router.callback_query(OnTestFilter(False), IsUser(is_candidate=True), F.data == 'main_candidate_menu_after_test')
async def candidate_after_test_main_menu_handler(call: CallbackQuery, state: FSMContext):
    await call.answer()
    text = WELCOME_CANDIDATE_TEXT
    keyboard = await welcome_menu_kb(call.from_user.id)
    await call.message.answer(text, reply_markup=keyboard.as_markup())