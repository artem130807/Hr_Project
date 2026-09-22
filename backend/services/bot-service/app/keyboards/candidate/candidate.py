from datetime import date, timedelta

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.loader import client
from app.api.endpoints import Endpoints


async def welcome_menu_kb(telegram_id):
    kb = InlineKeyboardBuilder()
    user = await client.get(Endpoints.get_user_by_telegram_id, telegram_id=telegram_id)
    progress = await client.get(Endpoints.get_user_progress, user_id=user['id'])
    if progress['test_disc']:
        kb.button(text=f"📋 Описание вакансии", callback_data='vacancy_description')
        kb.button(text=f"🏢 О компании", callback_data='company_info')
        kb.button(text=f"🌟 Корпоративная культура", callback_data='corp_culture')
        kb.button(text=f"📄 Мое резюме", callback_data='my_resume')
        
        kb.adjust(1,1,1,1)
        return kb
    # Ваш код должен выглядеть так:
    kb.button(text=f"📋 Описание вакансии {'' if not progress['vacancy_description'] else '- ✔'}", callback_data='vacancy_description')
    kb.button(text=f"🏢 О компании {'' if not progress['company_info'] else '- ✔'}", callback_data='company_info')
    kb.button(text=f"🌟 Корпоративная культура {'' if not progress['corp_culture'] else '- ✔'}", callback_data='corp_culture')
    kb.button(text=f"📄 Мое резюме {'' if not progress['my_resume'] else '- ✔'}", callback_data='my_resume')
    if progress['vacancy_description'] and progress['company_info'] and progress['corp_culture'] and progress['my_resume']:
        kb.button(text=f'➡️ Продолжить', callback_data='continue_to_test')
    kb.adjust(1,1,1)
    return kb


back_to_candidate_main_menu = InlineKeyboardBuilder()
back_to_candidate_main_menu.button(text='↪️ Ознакомлен(а)', callback_data='main_candidate_menu')


agreement_kb = InlineKeyboardBuilder()
agreement_kb.button(text='✅ Продолжить', callback_data='main_candidate_menu')
agreement_kb.button(text='❌ Отказаться', callback_data='candidate_disagree')
agreement_kb.adjust(1,1)


start_test = InlineKeyboardBuilder()
start_test.button(text='🕓 Начать?', callback_data='start_tests')


tests_completed_kb = InlineKeyboardBuilder()
tests_completed_kb.button(text='✅ Завершить', callback_data='tests_completed')

back_to_menu_after_test = InlineKeyboardBuilder()
back_to_menu_after_test.button(text='↪️ В меню', callback_data='main_candidate_menu_after_test')


async def pick_up_appointment_day_kb():
    kb = InlineKeyboardBuilder()
    today = date.today()
    date_from = today
    date_to = today + timedelta(days=7)

    # Получаем все слоты на ближайшие 7 дней
    slots = await client.get(
        Endpoints.get_all_availability,
        params = {
            "date_from": str(date_from),
            "date_to": str(date_to)
        }
    )

    # группируем по датам
    days_with_slots = {}
    for slot in slots:
        if not slot["is_booked"]:
            day_str = slot["date"]
            if day_str not in days_with_slots:
                days_with_slots[day_str] = []
            days_with_slots[day_str].append(slot)

    if not days_with_slots:
        kb.button(text="❌ Нет доступных дат", callback_data="no_available_days")
        kb.button(text='↪️ В меню', callback_data='main_candidate_menu_after_test')
        return kb.as_markup()

    # создаем кнопки по дням
    for day_str in sorted(days_with_slots.keys()):
        kb.button(
            text=f"📅 {day_str}",
            callback_data=f"pick_day:{day_str}"
        )

    kb.adjust(2)
    return kb.as_markup()


async def pick_up_appointment_time_kb(day: str):
    kb = InlineKeyboardBuilder()

    # Получаем слоты конкретного дня
    slots = await client.get(
        Endpoints.get_all_availability,
        params = {
            "date_from": str(day),
            "date_to": str(day)
        }
    )

    # фильтруем только свободные
    available_slots = [slot for slot in slots if not slot["is_booked"]]

    if not available_slots:
        kb.button(text="❌ Нет доступного времени", callback_data="no_available_time")
        kb.button(text="↩️ Назад", callback_data="back_to_day_select")
        kb.adjust(1)
        return kb.as_markup()

    # создаем кнопки по слотам времени
    for slot in available_slots:
        start = slot["start_time"][:-3]  # убираем секунды
        end = slot["end_time"][:-3]
        kb.button(
            text=f"{start} – {end}",
            callback_data=f"book_slot:{slot['id']}"
        )

    kb.button(text="↩️ Назад", callback_data="back_to_day_select")
    kb.adjust(2, 1)
    return kb.as_markup()


def first_agree_change_vacancy_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text='✅ Согласен', callback_data='agree_change_vacancy')
    kb.button(text='❌ Отказываюсь', callback_data='disagree_change_vacancy')
    kb.adjust(2)
    return kb.as_markup()


def offer_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text='✅ Согласен', callback_data='accept_offer')
    kb.button(text='❌ Отказываюсь', callback_data='reject_offer')
    kb.adjust(2)
    return kb.as_markup()
