import asyncio
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from app.filters.roles import IsUser
from app.filters.candidate_test import OnTestFilter
from app import config
from app.keyboards.candidate.candidate import back_to_candidate_main_menu, start_test, back_to_menu_after_test, tests_completed_kb, pick_up_appointment_day_kb, pick_up_appointment_time_kb
from app.api.endpoints import Endpoints
from app.utils.analytic_service import pass_checkpoint
from app.utils.text_splitter import split_message
from aiogram import Bot
from app.loader import client, redis_client, test_manager
from app.states.state import TestState
from app.api.enums import CandidateStatus, TestResultsType, TestType
from app.app_logging import logger


router = Router()


@router.callback_query(OnTestFilter(False), IsUser(is_candidate=True), F.data == 'company_info')
async def get_company_info_handler(call: CallbackQuery):
    text = config.GENERAL_COMPANY_INFO
    keyboard = back_to_candidate_main_menu
    await call.message.edit_text(text=text, reply_markup=keyboard.as_markup())
    candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id=call.from_user.id)
    if candidate:
        candidate_id = candidate['id']
        status = "откликнулся"
        status_uodated = await client.put(f'/candidate/{candidate_id}/status', json={"status": status})
        logger.info(f"Status {status} updated: {status_uodated}")
    await pass_checkpoint(call.from_user.id, 'company_info')


@router.callback_query(OnTestFilter(False), IsUser(is_candidate=True), F.data == 'vacancy_description')
async def get_vacancy_description_handler(call: CallbackQuery):
    candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id=call.from_user.id)
    if candidate:
        candidate_id = candidate['id']
    else:
        await call.message.edit_text('Кандидат не найден', reply_markup=back_to_candidate_main_menu.as_markup())
        return
    
    
    vacancy = await client.get(Endpoints.get_candidate_active_vacancy, candidate_id=candidate_id)
    if vacancy:
        vacancy_id = vacancy['id']
    else:
        await call.message.edit_text('Кандидат не привязан к вакансии', reply_markup=back_to_candidate_main_menu.as_markup())
        await call.message.answer(text=config.ERROR_MESSAGE)
        return
    
    description = await client.get(Endpoints.get_vacancy_description, vacancy_id=vacancy_id)
    if description:
        await pass_checkpoint(call.from_user.id, 'vacancy_description')
        status = "откликнулся"
        status_uodated = await client.put(f'/candidate/{candidate_id}/status', json={"status": status})
        logger.info(f"Status {status} updated: {status_uodated}")
        await call.message.edit_text(text=description, reply_markup=back_to_candidate_main_menu.as_markup(),parse_mode='HTML')
    else:
        await call.message.edit_text('Не удалось создать описание вакансии', reply_markup=back_to_candidate_main_menu.as_markup())
        return


@router.callback_query(OnTestFilter(False), IsUser(is_candidate=True), F.data == 'corp_culture')
async def get_corp_culture_info_handler(call: CallbackQuery):
    text = config.CORPORATE_CULTURE_INFO
    keyboard = back_to_candidate_main_menu
    await call.message.edit_text(text=text, reply_markup=keyboard.as_markup())
    candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id=call.from_user.id)
    if candidate:
        candidate_id = candidate['id']
        status = "откликнулся"
        status_uodated = await client.put(f'/candidate/{candidate_id}/status', json={"status": status})
        logger.info(f"Status {status} updated: {status_uodated}")
    await pass_checkpoint(call.from_user.id, 'corp_culture')


@router.callback_query(OnTestFilter(False), IsUser(is_candidate=True), F.data == 'my_resume')
async def get_candidate_resume_handler(call: CallbackQuery):
    candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id=call.from_user.id)
    if candidate:
        candidate_id = candidate['id']
    else:
        await call.message.edit_text('Кандидат не найден', reply_markup=back_to_candidate_main_menu.as_markup())
        return
    
    resume_desc = await client.get(Endpoints.get_candidate_resume, candidate_id=candidate_id)
    if not resume_desc:
        await call.message.edit_text('Не удалось создать описание резюме', reply_markup=back_to_candidate_main_menu.as_markup())
        return 
    text = resume_desc
    keyboard = back_to_candidate_main_menu
    parts = split_message(text)
    # если сообщение помещается — просто edit_text
    if len(parts) == 1:
        await call.message.edit_text(text=parts[0], reply_markup=keyboard.as_markup(), parse_mode='HTML')
    else:
        # первое редактируем, остальные отправляем следом
        await call.message.edit_text(text=parts[0], parse_mode='HTML')
        for part in parts[1:]:
            await call.message.answer(part, parse_mode='HTML')
        await call.message.answer('⬆️ Сообщение было разделено из-за длины', reply_markup=keyboard.as_markup())
    # await call.message.edit_text(text=text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
    status = "откликнулся"
    status_uodated = await client.put(f'/candidate/{candidate_id}/status', json={"status": status})
    logger.info(f"Status {status} updated: {status_uodated}")
    await pass_checkpoint(call.from_user.id, 'my_resume')


@router.callback_query(OnTestFilter(False), IsUser(is_candidate=True), F.data == 'continue_to_test')
async def confirmation_test_start_handler(call: CallbackQuery, state: FSMContext):
    telegram_id = str(call.from_user.id)
    vacancy = await client.get(Endpoints.get_vacancy_by_telegram_id, telegram_id=telegram_id)
    if not vacancy:
        await call.message.answer(text=config.ERROR_MESSAGE)
        return
    vacancy_id = vacancy['id']
    test_ids = await client.get(Endpoints.list_tests_for_vacancy, vacancy_id=vacancy_id)
    if not test_ids:
        text = config.WAIT_FOR_HR_ANSWER_TEXT
        keyboard = back_to_menu_after_test

        #Заполняем ai поля кандидата, постим отклик
        candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id=telegram_id)
        await client.post(
            "/candidate/fill-info",
            json={"candidate_id": candidate['id']}
        )
        await client.post(
            "/negotiation",
            json={"candidate_id": candidate['id']}
        )

        await call.message.edit_text(text, reply_markup=keyboard.as_markup())
    else:
        await state.update_data(test_ids=test_ids)
        await state.set_state(TestState.test)
        text = '⚠️ Вам потребуется пройти несколько тестов, на время прохождения остальной функционал бота будет отключен'
        keyboard = start_test
        await call.message.edit_text(text=text, reply_markup=keyboard.as_markup())


@router.callback_query(IsUser(is_candidate=True), F.data == 'candidate_disagree')
async def candidate_disagree_handler(call: CallbackQuery):
    await call.message.edit_text('Мы не будем хранить ваши данные.')



# ==============================
#          Tests
# ==============================

@router.callback_query(IsUser(is_candidate=True), F.data == 'start_tests')
async def first_test_handler(call: CallbackQuery, state: FSMContext):
    user_id = str(call.from_user.id)
    test = await test_manager.start_tests(user_id)
    if not test:
        text = config.WAIT_FOR_HR_ANSWER_TEXT
        #resend to hr
        keyboard = back_to_menu_after_test
        await call.message.edit_text(text, reply_markup=keyboard.as_markup())
        return
    
    candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id=user_id)
    if candidate:
        candidate_id = candidate['id']
        status = "тест: отправлен"
        status_uodated = await client.put(f'/candidate/{candidate_id}/status', json={"status": status})
        logger.info(f"Status {status} updated: {status_uodated}")

    await call.message.edit_text(text=test.get_instruction())

    if test.test_type == TestType.url.value:
        await state.set_state(TestState.result)
        logger.info("State TestState.result has been set")

    elif test.test_type == TestType.questions.value:
        question = await test_manager.start_questions(user_id)
        if not question:
            await call.message.edit_text(text=config.ERROR_MESSAGE)
            return
        await call.message.answer(text=question.text)
        await state.set_state(TestState.question)
        logger.info("State TestState.question has been set")
    

@router.message(OnTestFilter(True), IsUser(is_candidate=True), TestState.result)
async def get_test_results_handler(message: Message, state: FSMContext, bot: Bot):
    test = await test_manager.validate_results(message)
    if not test:
        await message.answer('⚠️ Убедитесь, что данные были отправлены в правильном формате и отправьте еще раз')
        return
    user_id = str(message.from_user.id)
    candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id = user_id)
    candidate_id = candidate['id']
    test_id = test.id
    comment = None
    score = None
    photo_file_id = None

    if test.results_type == TestResultsType.text:
        comment = message.text

    elif test.results_type == TestResultsType.screenshot_text:
        comment = message.caption
        photo_file_id = message.photo[-1].file_id

    elif test.results_type == TestResultsType.screenshot:
        photo_file_id = message.photo[-1].file_id

    elif test.results_type == TestResultsType.external_processing_result:
        pass

    payload = {
        "candidate_id": candidate_id,
        "test_id": test_id,
        "has_image": bool(photo_file_id),
        "score": score,
        "comment": comment
    }
    result = await client.post(Endpoints.post_test_results, json=payload)

    if photo_file_id and result:
        result_id = result.get("id")
        if result_id:
            tg_file = await bot.get_file(photo_file_id)
            file_bytes = await bot.download_file(tg_file.file_path)
            image_bytes = file_bytes.read()
            await client.post_file(
                Endpoints.upload_test_result_image,
                image_bytes=image_bytes,
                content_type="image/jpeg",
                result_id=result_id,
            )
    
    next_test = await test_manager.next_test(user_id)
    if not next_test:
        await state.clear()
        keyboard = tests_completed_kb
        text = config.TESTS_COMPLETED
        await message.answer(text, reply_markup=keyboard.as_markup())
        return
    
    await message.answer(text=next_test.get_instruction())

    if next_test.test_type == TestType.questions.value:
        question = await test_manager.start_questions(user_id)
        if not question:
            await message.answer(text=config.ERROR_MESSAGE)
            return
        await message.answer(text=question.text)
        await state.set_state(TestState.question)


@router.message(OnTestFilter(True), IsUser(is_candidate=True), TestState.question)
async def get_question_answer_handler(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not message.text:
        await message.answer("⚠️ Ответ должен быть текстовым сообщением")
        return
    
    question = await test_manager.get_current_question(user_id)
    question_id = question.id
    test = await test_manager.get_current_test(user_id)
    test_id = test.id

    candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id = user_id)
    candidate_id = candidate['id']

    text = message.text
    score = None

    payload = {
        "candidate_id": candidate_id,
        "question_id": question_id,
        "result_id": None,
        "answer_text": text,
        "answer_score": score
    }
    await client.post(Endpoints.create_question_answer, json=payload)

    next_question = await test_manager.next_question(user_id)
    if not next_question:
        await state.clear()
        payload = {
            "candidate_id": candidate_id,
            "test_id": test_id,
            "score": None,
            "comment": None
        }
        await client.post(Endpoints.post_test_results, json=payload)

        next_test = await test_manager.next_test(user_id)
        if not next_test:
            keyboard = tests_completed_kb
            text = config.TESTS_COMPLETED
            await message.answer(text, reply_markup=keyboard.as_markup())
            status = "тест: пройден"
            status_uodated = await client.put(f'/candidate/{candidate_id}/status', json={"status": status})
            logger.info(f"Status {status} updated: {status_uodated}")
            return
        
        await message.answer(text=next_test.get_instruction())

        if next_test.test_type == TestType.url.value:
            await state.set_state(TestState.result)

        elif next_test.test_type == TestType.questions.value:
            question = await test_manager.start_questions(user_id)
            if not question:
                await message.answer(text=config.ERROR_MESSAGE)
                return
            await message.answer(text=question.text)
            await state.set_state(TestState.question)
    await message.answer(text=next_question.text)


@router.callback_query(IsUser(is_candidate=True), F.data == 'tests_completed')
async def tests_completed_handler(call: CallbackQuery, state: FSMContext):
    user_id = str(call.from_user.id)
    # await pass_checkpoint(user_id, "test_adizes")
    text = config.WAIT_FOR_HR_ANSWER_TEXT
    keyboard = back_to_menu_after_test
    await pass_checkpoint(user_id, 'test_disc')

    #Заполняем ai поля кандидата, постим отклик
    candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id=user_id)
    await client.post(
        "/candidate/fill-info",
        json={"candidate_id": candidate['id']}
    )
    await client.post(
        "/negotiation",
        json={"candidate_id": candidate['id']}
    )

    await call.message.edit_text(text, reply_markup=keyboard.as_markup())


# ==============================
#          Schedule
# ==============================

@router.callback_query(IsUser(is_candidate=True), F.data.startswith('pick_day:'))
async def pick_day_candidate_handler(call: CallbackQuery):
    day = call.data.split('pick_day:')[1]
    kb = await pick_up_appointment_time_kb(day)
    await call.message.edit_text(text=config.SCHEDULE_APPOINTMENT, reply_markup=kb)


@router.callback_query(IsUser(is_candidate=True), F.data == 'back_to_day_select')
async def select_day_handler(call: CallbackQuery):
    await call.message.edit_text(text=config.SCHEDULE_APPOINTMENT, reply_markup = await pick_up_appointment_day_kb())


@router.callback_query(IsUser(is_candidate=True), F.data.startswith('book_slot:'))
async def book_slot_handler(call: CallbackQuery):
    slot_id = call.data.split('book_slot:')[1]

    # Получаем слот
    slot = await client.get(f'/availability/{slot_id}')
    if not slot:
        await call.message.edit_text("❌ Слот не найден.")
        return

    # Получаем кандидата по telegram_id
    candidate = await client.get(
        Endpoints.get_candidate_by_telegram_id,
        telegram_id=str(call.from_user.id)
    )
    if not candidate:
        await call.message.edit_text("❌ Кандидат не найден.")
        return
    candidate_id = candidate['id']

    # Бронируем слот
    result = await client.post(
        f"/availability/book/{slot_id}/{candidate['id']}"
    )
    if not result:
        await call.message.edit_text("❌ Не удалось забронировать слот.")
        return

    # Форматируем дату и время
    date_str = datetime.strptime(slot["date"], "%Y-%m-%d").strftime("%d.%m.%Y")
    start_time = slot["start_time"][:5]  # "HH:MM"
    end_time = slot["end_time"][:5]

    # Отправляем подтверждение
    await call.message.edit_text(
        text=(
            f"✅ Ваша встреча назначена на <b>{date_str}</b>\n"
            f"🕓 Время: <b>{start_time}–{end_time}</b>\n"
            f"Адрес: {config.COMPANY_ADRESS}"
        ),
        parse_mode="HTML"
    )
    status = "собес"
    status_uodated = await client.put(f'/candidate/{candidate_id}/status', json={"status": status})
    logger.info(f"Status {status} updated: {status_uodated}")



# ==============================
#        Change vacancy
# ==============================

@router.callback_query(IsUser(is_candidate=True), F.data == 'agree_change_vacancy')
async def agree_change_vacancy_handler(call: CallbackQuery):
    user_id = str(call.from_user.id)
    candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id=user_id)
    await client.post(
        "/candidate/fill-info",
        json={"candidate_id": candidate['id']}
    )
    await client.post(
        "/negotiation",
        json={"candidate_id": candidate['id']}
    )

    text = config.WAIT_FOR_HR_ANSWER_TEXT
    keyboard = back_to_menu_after_test

    await call.message.edit_text(text, reply_markup=keyboard.as_markup())


@router.callback_query(IsUser(is_candidate=True), F.data == 'disagree_change_vacancy')
async def thinking_handler(call: CallbackQuery):
    text = "На данный момент у нас больше нет подходящих для вас вакансий, но мы напишем вам, если они появятся."

    candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id = str(call.from_user.id))
    candidate_id = candidate['id']
    await client.put(f'/candidate/{candidate_id}/archive')

    kb = back_to_menu_after_test.as_markup()
    await call.message.edit_text(text=text, reply_markup=kb)



# ==============================
#           Offer
# ==============================
@router.callback_query(IsUser(is_candidate=True), F.data == 'accept_offer')
async def accept_offer_handler(call: CallbackQuery):
    candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id=call.from_user.id)
    if candidate:
        candidate_id = candidate['id']
        # Acceptance is a hiring-funnel decision, not evidence of actual first day.
        status = CandidateStatus.offer_accepted.value
        status_uodated = await client.put(f'/candidate/{candidate_id}/status', json={"status": status})
        logger.info(f"Status {status} updated: {status_uodated}")
    text = "✅ Оффер принят. HR свяжется с вами для согласования фактической даты выхода."
    await call.message.edit_text(text=text)


@router.callback_query(IsUser(is_candidate=True), F.data == 'reject_offer')
async def reject_offer_handler(call: CallbackQuery):
    #to-do: change status to 
    text = "Спасибо за уделенное время!\nМы сообщим, если появятся новые вакансии, подходящие для вас."
    
    candidate = await client.get(Endpoints.get_candidate_by_telegram_id, telegram_id=str(call.from_user.id))
    candidate_id = candidate['id']
    status = "отказ"
    status_uodated = await client.put(f'/candidate/{candidate_id}/status', json={"status": status})
    logger.info(f"Status {status} updated: {status_uodated}")
    result = await client.put(f'/candidate/{candidate_id}/archive')

    await call.message.edit_text(text=config.ARCHIVE_CANDIDATE_TEXT)
