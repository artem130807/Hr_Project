from enum import Enum


class AdminRoles(str, Enum):
    """Panel / JWT roles: legacy HR roles + ERP role set."""

    # Native HR platform roles
    owner = "owner"
    hr = "hr"
    lead = "lead"
    art = "art"
    dev = "dev"
    # ERP roles (erp-backend seed + prod «Руководитель отдела»)
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
    """Hiring funnel statuses (flat enum; UI shows parent/child tree)."""

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
    full_documents = "Full documents"
    rejection = "отказ"
    started_work = "ВНР"
    resigned = "уволился"


class VnrHireStatus(str, Enum):
    """Lifecycle of a ВНР placement attributed to an HR user."""

    in_work = "in_work"
    left = "left"


# Terminal statuses → archive stage (except started_work → hired)
ARCHIVE_STATUSES = frozenset(
    {
        CandidateStatus.not_suitable,
        CandidateStatus.refused,
        CandidateStatus.rejection,
        CandidateStatus.resigned,
    }
)

class Gender(str, Enum):
    male = 'male'
    female = 'female'


class WorkExpirience(str, Enum):
    no_experience = 'noExperience'
    one_to_three = 'between1And3'
    three_to_six = 'between3And6'
    six_to_infinite = 'moreThan6'


class WorkFormat(str, Enum):
    """Work arrangement for vacancy filters."""
    remote = "remote"      # удалёнка
    office = "office"      # офис
    hybrid = "hybrid"      # гибрид
    field = "field"        # разъездной
    shift = "shift"        # сменный


class VacancyFilterAction(str, Enum):
    """HH status applied by auto-filter."""

    discard = "discard"  # отказ тем, кто не проходит фильтр
    consider = "consider"  # «подумать» тем, кто проходит фильтр


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
    screenshot = "скриншот"
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


class ResumeSearchStatus(str, Enum):
    skipped = 'skipped'
    invited = 'invited'
    unreachable = 'unreachable'
    pending = 'pending'  # Резюме найдено, но еще не оценено


class EvaluationStatus(str, Enum):
    pending = 'pending'  # Ожидает оценки
    evaluated = 'evaluated'  # Оценено успешно
    failed = 'failed'  # Ошибка при оценке


class CallConversationStatus(str, Enum):
    """HR outcome of a call. Set later by Whisper analysis — not T2 ATS callStatus."""

    pending = "pending"  # Определяется
    interested = "interested"  # Интерес
    interview = "interview"  # Собеседование
    callback = "callback"  # Перезвон
    rejected = "rejected"  # Отказ
    dropped = "dropped"  # Сброс


class HiringRequestStatus(str, Enum):
    """TZ workflow + legacy values kept for existing rows."""
    created = 'создана'           # Новая
    on_analysis = 'на анализе'
    approved = 'утверждена'
    published = 'опубликована'
    returned = 'возвращена на уточнение'
    closed = 'закрыта'
    cancelled = 'отменена'
    completed = 'завершена'       # legacy → treat as closed in UI
