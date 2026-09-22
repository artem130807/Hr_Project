from typing import Any
from datetime import date, datetime
import html

from app.db.v1.models import Candidate, Vacancy

def _safe(value: Any) -> str:
    """Привести значение к строке и эскейпить HTML; пустые -> '—'."""
    if value is None:
        return "—"
    if isinstance(value, (list, tuple)):
        return html.escape(", ".join(str(x) for x in value)) if value else "—"
    # datetime/date formatting
    if isinstance(value, (datetime, date)):
        return html.escape(value.isoformat())
    return html.escape(str(value))

def render_candidate_html_for_telegram(candidate: Candidate, vacancy: Vacancy) -> str:
    """
    Возвращает HTML-строку, совместимую с Telegram parse_mode='HTML'.
    """
    if candidate.gender == 'male':
        mapped_gender = 'мужчина'
    elif candidate.gender == 'female':
        mapped_gender = 'женщина'
    else:
        mapped_gender = None

    full_name = _safe(candidate.full_name)
    age = _safe(candidate.age)
    gender = _safe(mapped_gender) if mapped_gender else _safe('пол не указан')
    birth_date = _safe(candidate.birth_date)
    phone = _safe(candidate.phone_number)
    marital = _safe(candidate.marital_status.value)
    hobbies = _safe(candidate.hobbies)
    personal = _safe(candidate.personal_characteristics)

    hh_link = candidate.hh_resume_link if getattr(candidate, "hh_resume_link", None) else None
    hh_html = f'<a href="{html.escape(hh_link)}">Резюме на HH</a>' if hh_link else "—"

    relevant_exp = _safe(candidate.relevant_position_expirience)
    certain_exp = _safe(candidate.certain_position_expirience)
    other_exp = _safe(candidate.other_work_expirience)
    avg_len = _safe(candidate.average_service_length)
    total_exp = _safe(candidate.total_work_expirience)

    hard_skills = _safe(candidate.hard_skills)
    work_programs = _safe(candidate.work_programs)
    languages = _safe(candidate.languages)
    education = _safe(candidate.education)

    active_search = "Да" if getattr(candidate, "active_search", False) else "Нет"
    salary = _safe(candidate.salary_expectations)
    ai_comment = _safe(candidate.ai_comment)
    ai_score = _safe(candidate.ai_score)

    vacancy_name = _safe(vacancy.name)

    parts = []

    # header
    parts.append(f"<b>👤 {full_name}</b>")
    subtitle = []
    if age != "—":
        subtitle.append(f"{age} лет")
    if gender != "—":
        subtitle.append(f"{gender}")
    if subtitle:
        parts.append(f"<i>{html.escape(' · '.join(subtitle))}</i>")

    # 💼 Добавляем строку с вакансией
    parts.append(f"<b>Вакансия:</b> {vacancy_name}")

    # Контакты и основные
    parts.append(
        "<b>📞 Контакты:</b>\n"
        f"<b>Телефон:</b> {phone}\n"
        f"<b>Telegram:</b> {_safe(getattr(candidate, 'telegram_username', None))}\n"
        f"<b>Почта:</b> {_safe(getattr(candidate, 'email', None))}\n"
        f"<b>Семейное положение:</b> {marital}\n"
        f"<b>Дата рождения:</b> {birth_date}\n"
    )

    # Личное
    parts.append(
        "<b>💡 Личное:</b>\n"
        f"<b>Хобби:</b> {hobbies}\n"
        f"<b>Характер:</b> {personal}\n"
    )

    # Опыт и навыки
    parts.append(
        "<b>💼 Опыт и навыки:</b>\n"
        f"<b>Опыт (релевантный):</b> {relevant_exp}\n"
        f"<b>Опыт (конкретная позиция):</b> {certain_exp}\n"
        f"<b>Другой опыт:</b> {other_exp}\n"
        f"<b>Общий опыт:</b> {total_exp}\n"
        f"<b>Средняя длительность работы (лет):</b> {avg_len}\n"
        f"<b>Hard skills:</b> {hard_skills}\n"
        f"<b>Программы:</b> {work_programs}\n"
        f"<b>Языки:</b> {languages}\n"
    )

    # Образование
    parts.append(f"<b>🎓 Образование:</b>\n{education}")

    # Дополнительно
    parts.append(
        "<b>🔎 Дополнительно:</b>\n"
        f"<b>З/п ожидания:</b> {salary}\n"
        f"<b>Активный поиск:</b> {html.escape(active_search)}\n"
        f"<b>Ссылка:</b> {hh_html}\n"
        f"<b>AI комментарий:</b> {ai_comment}\n"
        f"<b>AI оценка:</b> {ai_score}/100\n"
    )

    message = "\n\n".join(parts)
    return message