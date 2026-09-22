from enum import Enum


class AdminRoles(str, Enum):
    """Panel / JWT roles: legacy HR roles + ERP role set."""

    owner = "owner"
    hr = "hr"
    lead = "lead"
    art = "art"
    dev = "dev"
    superadmin = "superadmin"
    admin = "admin"
    manager = "manager"
    leader = "leader"
    dept_leader = "dept_leader"
    senior_manager = "senior_manager"


class BotRoles(str, Enum):
    owner = "owner"
    hr = "hr"
    lead = "lead"
    art = "art"
    candidate = "candidate"
    employee = "employee"


class CandidateStatus(str, Enum):
    cold_contact = "холодный контакт"
    not_suitable = "не подходит"
    refused = "отказался"
    applied = "откликнулся"
    test_sent = "тест: отправлен"
    test_failed = "тест: не прошли"
    test_passed = "тест: пройден"
    interview = "собес"
    consider = "подумать"
    rejection = "отказ"
    started_work = "ВНР"
    resigned = "уволился"


class Gender(str, Enum):
    male = 'male'
    female = 'female'


class WorkExpirience(str, Enum):
    no_experience = 'noExperience'
    one_to_three = 'between1And3'
    three_to_six = 'between3And6'
    six_to_infinite = 'moreThan6'


class UpdateDate(str, Enum):
    week = '7-14 дней'
    month = '30 дней'
    year = '1 год'


class TestType(str, Enum):
    url = 'url'
    questions = 'Вопросно-ответная форма'


class TestResultsType(str, Enum):
    text = "текстовый результат"
    screenshot_text = "текстовый результат + скриншот"
    external_processing_result = "результат обрабатывается сторонним сервисом"


class MaritalStatus(str, Enum):
    married = "в браке"
    single = "не в браке"
    divorced = "в разводе"
    widowed = "вдовец/вдова"


class Departments(str, Enum):
    hr = 'hr'
    logistics = 'логистический'
    paperworks = 'делопроизводственный'
    legals = 'юридический'
    billing = 'бухгалтерия'
    art = 'art'
    it = 'IT'
    development = 'развитие'


class CandidateStage(str, Enum):
    employment = 'в процессе найма'
    archieved = 'архивирован'
    blacklisted = 'в черном списке'
    hired = 'нанят'