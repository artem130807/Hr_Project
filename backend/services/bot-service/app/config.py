import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_SERVICE_URL = os.getenv('DB_SERVICE_URL')

REDIS_SERVICE_URL = os.getenv('REDIS_SERVICE_URL')

ALGORITHM = "RS256"
JWKS_URL = os.getenv("JWKS_URL")

HR_CONTACT = '@(вставим контакт вашего hr менеджера)'

WELCOME_CANDIDATE_TEXT = ("Рады приветствовать вас в Hr платформе!\n"
"Здесь проходит подбор: анкета, тесты и связь с HR.\n\n"
"Чтобы продолжить — откройте разделы снизу."
)

WELCOME_ADMIN_TEXT = 'id: <code>{telegram_id}</code>\nДобрый день!\nЭто рекрутинговый бот. Здесь вы будете видеть кандидатов, прошедших тесты и можете выполнять действия для их обработки.\nХорошего рабочего дня!'

GENERAL_COMPANY_INFO = (
    "Hr платформа помогает пройти подбор в одном месте.\n"
    "Дальше HR расскажет об условиях, графике и следующих шагах."
)

COMPANY_ADRESS = "адрес компании"
CORPORATE_CULTURE_INFO = (
    "Hr платформа — общий контур подбора для кандидата и HR.\n"
    "Дальше вы увидите шаги отклика, тесты и сообщения от рекрутера."
)
AGREEMENT_TEXT = 'Нажимая кнопку «Продолжить», вы даёте согласие на обработку ваших персональных данных, включая указанные в анкете сведения, в соответствии с Федеральным законом №152-ФЗ «О персональных данных» в целях обработки заявки и обратной связи.\nСогласие может быть отозвано вами в любое время путем письменного уведомления.'

DISC_TEST_INSTRUSTION = 'Пройдите тестирование по ссылке https://ttisi.ru/testdisc, скопируйте текстовый результат и сделайте его скриншот и направьте ответным сообщением.'

ADIZES_TEST_INSTRUCTION = 'Пройдите тестирование по ссылке https://s.adizes.org/seminar/paei-c/xZd0My2FMInjUOLsvpBoOBjO5v200ZJO и укажите в форме e-mail, который пришлёт HR.'

WAIT_FOR_HR_ANSWER_TEXT = 'В ближайшее время с вами свяжется наш hr менеджер, ожидайте, пожалуйста.'

ERROR_MESSAGE = 'Произошла ошибка, сделайте скриншот и обратитесь к @istendlay'

EXTERNAL_RPOCESSED_TEST_PASSED_COMMAND = '/ready'

TEST_WITH_QUESTIONS_EXTRA_INFO = '📩 Направляйте ответы на вопросы ответным сообщением.'

TESTS_COMPLETED = '🏁 Вы прошли все тесты!'


BOT_SERVICE_CLIENT_ID = os.getenv("BOT_SERVICE_CLIENT_ID")
BOT_SERVICE_CLIENT_SECRET = os.getenv("BOT_SERVICE_CLIENT_SECRET")

NO_NEGOTIATIONS_MORE = '🏁 Вы просмотрели все отклики!'

ARCHIVE_CANDIDATE_TEXT = 'Спасибо за уделенное время! К сожалению мы не можем пригласить вас на данную вакансию, но готовы рассмотреть вашу кандидатуру в будущем.\nНе удаляйте чат с ботом, чтобы мы могли сообщить о новой подходящей для вас вакансии!\nС уважением, команда подбора'

BLACKLIST_CANDIDATE_TEXT = 'Спасибо за уделенное время! К сожалению мы не можем пригласить вас на данную вакансию.'

SCHEDULE_APPOINTMENT = '✅ Вас пригласили на встречу! Выберите удобный день:'
