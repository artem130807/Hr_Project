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
    offer_accepted = "оффер принят"
    rejection = "отказ"
    started_work = "ВНР"
    resigned = "уволился"


class WorkFormat(str, Enum):
    remote = 'удалённый'
    hybrid = 'гибридный'
    office = 'офис'
    shift = 'сменный'


class EmploymentType(str, Enum):
    full = 'полная'
    part_time = 'частичная'
    temporary = 'временная'


class TestType(str, Enum):
    url = 'url'
    questions = 'Вопросно-ответная форма'


class TestResultsType(str, Enum):
    text = "текстовый результат"
    screenshot_text = "текстовый результат + скриншот"
    screenshot = "скриншот"
    external_processing_result = "результат обрабатывается сторонним сервисом"
