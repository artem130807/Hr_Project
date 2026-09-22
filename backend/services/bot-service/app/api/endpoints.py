class Endpoints:
    # ---------- Bot Users ----------
    get_all_users = '/users'
    user = '/user/{id}'
    post_user = '/user'
    get_user_by_telegram_id = '/telegram/{telegram_id}/user'
    get_candidate_by_telegram_id = '/telegram/{telegram_id}/candidate'
    get_user_progress = '/progress/{user_id}'
    patch_user_progress = '/progress/{telegram_id}'

    # ---------- Candidates ----------
    list_candidates = '/candidates'
    candidate = '/candidate/{candidate_id}'
    get_candidate_active_vacancy = '/candidate/{candidate_id}/active-vacancy'
    get_candidate_and_active_vacancy = '/candidate/{relation_id}/vacancy'
    candidate_vacancy_relation = '/candidate/vacancy/{relation_id}'
    get_candidate_resume = '/candidate/{candidate_id}/resume'
    get_candidate_tests = '/candidate/{candidate_id}/tests'  # новые результаты тестов по кандидату
    list_candidate_vacancies = '/candidate/{candidate_id}/vacancies'
    candidate_vacancy_relation = '/candidate/vacancy/{relation_id}'
    create_candidate_vacancy = '/candidate/vacancy'
    list_candidate_test_results = '/candidate/{candidate_id}/results'

    # ---------- Tokens ----------
    create_invite_token = '/invite_token'
    get_invite_token = '/invite_token/{token}'

    # ---------- Vacancies ----------
    get_vacancy_description = '/vacancy/{vacancy_id}/description'
    list_vacancies = '/vacancies'
    post_vacancy = '/vacancy'
    get_vacancy = '/vacancy/{vacancy_id}'
    get_vacancy_by_telegram_id = '/vacancy/active/telegram/{telegram_id}'
    update_vacancy = '/vacancy/{vacancy_id}'
    delete_vacancy = '/vacancy/{vacancy_id}'

    add_tests_to_vacancy = '/vacancy/{vacancy_id}/add_tests'
    list_tests_for_vacancy = '/vacancy/{vacancy_id}/tests'
    update_tests_for_vacancy = '/vacancy/{vacancy_id}/update_tests'

    # ---------- Tests ----------
    list_tests = '/tests'
    get_test = '/test/{test_id}'
    get_question = '/question/{question_id}'
    create_test = '/test'
    delete_test = '/test/{test_id}'
    get_test_questions = '/test/{test_id}/questions'
    post_test_results = '/test/results'
    get_test_result_by_result_id = '/test/results/{result_id}'
    get_test_results_by_test_id = '/test/{test_id}/results'
    upload_test_result_image = '/test/results/{result_id}/image'
    create_question_answer = '/test/question-answers'
    question_answer_by_id = '/test/question-answers/{answer_id}'
    question_answers_for_result = '/test/results/{result_id}/answers'

    # ---------- Web Admin Panel Users ----------
    get_admin = '/admin/user/{admin_id}'

    # ---------- Schedule -----------------------
    get_hr_availability = '/availability/hr/{hr_id}'
    get_all_availability = '/availability/all'
    

class AdminEndpoints:
    pass
