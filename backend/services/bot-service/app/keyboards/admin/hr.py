from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.loader import client, redis_client
from app.api.endpoints import Endpoints
from app.loader import negotiation_manager

async def handle_candidate_kb(candidate_id: int) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text='📅 Пригласить на встречу', callback_data=f"schedule_appointment_id:{candidate_id}")
    kb.button(text='📂 Перевести в архив', callback_data=f"archieve_id:{candidate_id}")
    kb.button(text='🚫 В черный список', callback_data=f"blacklist_id:{candidate_id}")
    kb.button(text='🔄 На другую вакансию', callback_data=f"change_vacancy_id:{candidate_id}")
    kb.button(text='Меню', callback_data='back_to_hr_main_menu')

    kb.adjust(1)
    return kb


def hr_back_to_menu_kb() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text='↪️ В меню', callback_data="back_to_hr_main_menu")
    return kb


def confirm_kb(action: str, candidate_id: int, current_callback_data: str):
    kb =  InlineKeyboardBuilder()
    kb.button(text='✅ Подтвердить', callback_data=f"confirm_{action}_id:{candidate_id}")
    kb.button(text='❌ Отмена', callback_data=current_callback_data)
    return kb


async def change_vacancy_kb(candidate_id: int) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    vacancies = await client.get(Endpoints.list_vacancies)
    if not isinstance(vacancies, list):
        raise Exception("Vacancies not found")
    for vacancy in vacancies:
        kb.button(text=vacancy['name'], callback_data=f"change_vacancy_to_id:{vacancy['id']}_for_id:{candidate_id}")
    return kb


async def hr_main_menu() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()

    neg_count = await negotiation_manager.count()

    kb.button(text=f'📩 Отклики ({neg_count})', callback_data='negotiations')
    return kb
    

async def pick_up_vacancy_kb(candidate_id: int) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    vacancies = await client.get('/vacancies')
    if not vacancies:
        return None
    for vacancy in vacancies:
        kb.button(text=vacancy['name'], callback_data=f"vacancy-id:{vacancy['id']}_candidate-id:{candidate_id}")
    kb.adjust(1)
    return kb