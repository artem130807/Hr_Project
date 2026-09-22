from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone, date
import re
from app.schemas.v1.candidates import CandidateCreate
from app.enums.v1.enums import CandidateStage, MaritalStatus, Gender, WorkExpirience, UpdateDate
from app.app_logging import logger

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_TYPE_IDS = {"cell", "home", "work", "phone"}
_TELEGRAM_TYPE_IDS = {"telegram", "tg"}


def safe_str(x):
    return str(x).strip() if x else None


def format_hh_full_name(
    last_name: Optional[str] = None,
    first_name: Optional[str] = None,
    middle_name: Optional[str] = None,
    *,
    resume: Optional[dict] = None,
) -> Optional[str]:
    """Фамилия Имя Отчество — стандарт ФИО (HH: last_name / first_name / middle_name)."""
    if isinstance(resume, dict):
        last_name = resume.get("last_name")
        first_name = resume.get("first_name")
        middle_name = resume.get("middle_name")
    parts = [safe_str(last_name), safe_str(first_name), safe_str(middle_name)]
    name = " ".join(p for p in parts if p)
    return name or None


def safe_get(d: dict, key: str, default=None):
    return d.get(key) if isinstance(d, dict) else default


def safe_parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str or not isinstance(date_str, str):
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.date()
        except ValueError:
            continue
    return None


def fix_tz_offset(dt_str: str) -> str:
    if not dt_str or not isinstance(dt_str, str):
        return ""
    if dt_str.endswith("Z"):
        dt_str = dt_str.replace("Z", "+00:00")
    if len(dt_str) >= 5 and dt_str[-5] in "+-" and dt_str[-3] != ":":
        return dt_str[:-2] + ":" + dt_str[-2:]
    return dt_str


def map_months_to_work_experience(months: Optional[int]) -> Optional[WorkExpirience]:
    if not isinstance(months, int):
        return None
    if months < 12:
        return WorkExpirience.no_experience
    elif 12 <= months < 36:
        return WorkExpirience.one_to_three
    elif 36 <= months < 72:
        return WorkExpirience.three_to_six
    return WorkExpirience.six_to_infinite


def _contact_type_id(contact: dict) -> Optional[str]:
    t = contact.get("type")
    if isinstance(t, dict):
        return safe_str(t.get("id"))
    if isinstance(t, str):
        return safe_str(t)
    return None


def _contact_raw_value(contact: dict) -> Optional[str]:
    value = contact.get("contact_value")
    if value is None:
        value = contact.get("value")
    if value is None:
        value = contact.get("url")
    if isinstance(value, dict):
        value = (
            value.get("formatted")
            or value.get("username")
            or value.get("number")
            or value.get("value")
            or value.get("url")
        )
    return safe_str(value)


def normalize_email(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).strip().lower()
    if not s or not _EMAIL_RE.match(s):
        return None
    return s


def normalize_telegram_username(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    lower = s.lower()
    for prefix in (
        "https://t.me/",
        "http://t.me/",
        "https://telegram.me/",
        "http://telegram.me/",
        "t.me/",
        "telegram.me/",
    ):
        if lower.startswith(prefix):
            s = s[len(prefix):]
            break
    s = s.lstrip("@").split("/")[0].split("?")[0].strip()
    if not s or " " in s or len(s) > 32:
        return None
    return f"@{s}"


def _normalize_phone(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    formatted = (
        str(raw).replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    )
    if formatted.startswith("8"):
        formatted = "+7" + formatted[1:]
    elif not formatted.startswith("+"):
        formatted = "+7" + formatted
    return formatted or None


@dataclass(frozen=True)
class ResumeContacts:
    phone: Optional[str] = None
    email: Optional[str] = None
    telegram: Optional[str] = None


def _item_web_link(item: dict) -> Optional[str]:
    links = item.get("links") if isinstance(item.get("links"), dict) else {}
    return safe_str(links.get("web")) or safe_str(item.get("url"))


def _classify_contact_item(item: dict) -> tuple[Optional[str], Optional[str]]:
    """Return (kind, value) where kind is phone|email|telegram."""
    type_id = (_contact_type_id(item) or "").lower()
    kind = (safe_str(item.get("kind")) or "").lower()
    raw = _contact_raw_value(item)
    web_link = _item_web_link(item)
    blob = " ".join(x for x in (raw, web_link, type_id, kind) if x).lower()

    if type_id in _TELEGRAM_TYPE_IDS or "telegram" in kind or "t.me/" in blob or "telegram.me/" in blob:
        return "telegram", raw or web_link
    if type_id == "email" or kind == "email":
        return "email", raw
    if kind == "phone" or type_id in _PHONE_TYPE_IDS:
        return "phone", raw

    email = normalize_email(raw)
    if email:
        return "email", email
    telegram = normalize_telegram_username(raw or web_link)
    if telegram and "@" in (raw or "") and "." not in (raw or "").split("@")[-1]:
        return "telegram", raw or web_link
    if telegram and (raw or web_link or "").lower().find("t.me") >= 0:
        return "telegram", raw or web_link
    return None, raw


def extract_hh_resume_contacts(resume_or_contacts) -> ResumeContacts:
    """Phone, email and Telegram from HH resume `contact` + `site`."""
    phone = email = telegram = None
    contacts: list = []
    sites: list = []

    if isinstance(resume_or_contacts, dict):
        raw_contacts = resume_or_contacts.get("contact")
        raw_sites = resume_or_contacts.get("site")
        if isinstance(raw_contacts, list):
            contacts = raw_contacts
        if isinstance(raw_sites, list):
            sites = raw_sites
        top_email = normalize_email(resume_or_contacts.get("email"))
        if top_email:
            email = top_email
    elif isinstance(resume_or_contacts, list):
        contacts = resume_or_contacts
    else:
        return ResumeContacts()

    for item in (*contacts, *sites):
        if not isinstance(item, dict):
            continue
        try:
            kind, value = _classify_contact_item(item)
            if kind == "telegram" and not telegram:
                telegram = normalize_telegram_username(value)
            elif kind == "email" and not email:
                email = normalize_email(value)
            elif kind == "phone" and not phone:
                phone = _normalize_phone(value)
        except Exception:
            continue

    return ResumeContacts(phone=phone, email=email, telegram=telegram)


def parse_hh_resume_to_candidate(resume_data: dict) -> CandidateCreate:
    if not isinstance(resume_data, dict):
        raise ValueError("resume_data must be dict")

    # ===== Контакты (телефон, почта, telegram из contact и site) =====
    resume_contacts = extract_hh_resume_contacts(resume_data)
    formatted_phone = resume_contacts.phone
    telegram_username = resume_contacts.telegram
    email = resume_contacts.email

    # ===== Возраст =====
    age = resume_data.get("age")
    birth_date_str = safe_get(resume_data, "birth_date")
    birth_date_parsed = safe_parse_date(birth_date_str)
    if not age and birth_date_parsed:
        today = datetime.today().date()
        age = today.year - birth_date_parsed.year - ((today.month, today.day) < (birth_date_parsed.month, birth_date_parsed.day))

    # ===== resume_update_date =====
    resume_update_date = None
    updated_at_str = resume_data.get("updated_at")
    if updated_at_str:
        try:
            fixed_str = fix_tz_offset(updated_at_str)
            updated_at = datetime.fromisoformat(fixed_str)
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            delta_days = (datetime.now(timezone.utc) - updated_at).days
            if delta_days <= 14:
                resume_update_date = UpdateDate.week
            elif delta_days <= 30:
                resume_update_date = UpdateDate.month
            else:
                resume_update_date = UpdateDate.year
        except Exception as e:
            logger.warning(f"Failed to parse updated_at '{updated_at_str}': {e}")

    # ===== Опыт работы =====
    other_work_experience = []
    experiences = resume_data.get("experience") or []
    if isinstance(experiences, list):
        for exp in experiences:
            if not isinstance(exp, dict):
                continue
            try:
                parts = []
                position = safe_get(exp, "position")
                company = safe_get(exp, "company")
                if position:
                    parts.append(f"Должность: {position}")
                if company:
                    parts.append(f"Компания: {company}")

                industries = safe_get(exp, "industries", [])
                if not industries and safe_get(exp, "industry"):
                    industries = [safe_get(exp, "industry")]
                if isinstance(industries, list) and industries:
                    name = safe_get(industries[0], "name")
                    if name:
                        parts.append(f"Отрасль: {name}")

                area = safe_get(exp, "area")
                if isinstance(area, dict):
                    area_name = safe_get(area, "name")
                    if area_name:
                        parts.append(f"Регион: {area_name}")

                start, end = safe_get(exp, "start"), safe_get(exp, "end")
                if start or end:
                    date_str = f"{start or '?'} — {end or 'н.в.'}"
                    parts.append(f"Период: {date_str}")

                desc = safe_get(exp, "description")
                if desc:
                    parts.append(f"Описание: {desc}")

                if parts:
                    other_work_experience.append("\n".join(parts))
            except Exception as e:
                logger.warning(f"Failed to parse experience: {e}")

    # ===== Языки =====
    languages = []
    langs = resume_data.get("language") or []
    if isinstance(langs, list):
        for lang in langs:
            if isinstance(lang, dict):
                name = safe_get(lang, "name")
                if name:
                    languages.append(name)
            elif isinstance(lang, str):
                languages.append(lang)

    # ===== Образование =====
    education_list = []
    education = resume_data.get("education") or {}
    if isinstance(education, dict):
        for v in education.values():
            if isinstance(v, list):
                for e in v:
                    if isinstance(e, dict):
                        val = safe_get(e, "name") or safe_get(e, "organization") or safe_get(e, "result")
                        if val:
                            education_list.append(val)
            elif isinstance(v, str):
                education_list.append(v)
    elif isinstance(education, list):
        education_list.extend([str(x) for x in education if x])

    # ===== Навыки =====
    hard_skills = []
    skills = resume_data.get("skill_set") or []
    if isinstance(skills, list):
        for s in skills:
            if isinstance(s, dict):
                name = safe_get(s, "name")
                if name:
                    hard_skills.append(name)
            elif isinstance(s, str):
                hard_skills.append(s)

    # ===== Прочие =====
    salary = safe_get(resume_data, "salary")
    salary_expectations = safe_get(salary, "amount") if isinstance(salary, dict) else None

    gender_raw = safe_get(resume_data, "gender")
    gender = None
    if isinstance(gender_raw, dict):
        gender = {"male": Gender.male, "female": Gender.female}.get(gender_raw.get("id"))
    elif isinstance(gender_raw, str):
        gender = {"male": Gender.male, "female": Gender.female}.get(gender_raw)

    total_exp = safe_get(resume_data, "total_experience")
    total_months = safe_get(total_exp, "months") if isinstance(total_exp, dict) else None
    total_work_expirience = map_months_to_work_experience(total_months)

    # ===== Средняя длина работы =====
    average_service_length = None
    try:
        if experiences:
            months_all, valid = 0, 0
            for exp in experiences:
                start = safe_parse_date(safe_get(exp, "start"))
                end = safe_parse_date(safe_get(exp, "end")) or datetime.today().date()
                if start:
                    delta = (end.year - start.year) * 12 + (end.month - start.month)
                    if delta >= 0:
                        months_all += delta
                        valid += 1
            if valid:
                average_service_length = round((months_all / valid) / 12, 1)
    except Exception:
        pass

    # ===== Финальный объект =====
    return CandidateCreate(
        full_name=format_hh_full_name(resume=resume_data),
        phone_number=formatted_phone,
        telegram_username=telegram_username,
        email=email,
        age=age,
        birth_date=birth_date_parsed,
        gender=gender,
        languages=languages,
        education=education_list,
        hard_skills=hard_skills,
        salary_expectations=salary_expectations,
        hh_resume_link=safe_get(resume_data, "alternate_url", ""),
        stage=CandidateStage.employment,
        marital_status=MaritalStatus.single,
        hobbies=[],
        personal_characteristics=None,
        relevant_position_expirience=None,
        certain_position_expirience=None,
        total_work_expirience=total_work_expirience,
        other_work_expirience=other_work_experience,
        average_service_length=average_service_length,
        work_programs=[],
        resume_update_date=resume_update_date,
        active_search=True,
        ai_comment=None,
        ai_score=None,
    )
