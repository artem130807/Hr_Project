def safe_get(d, *keys, default=None):
    """
    Безопасно получает значение из вложенного словаря.
    Пример: safe_get(data, 'gender', 'name') -> вернёт data['gender']['name'] или default, если что-то None.
    """
    for key in keys:
        if isinstance(d, dict) and d is not None:
            d = d.get(key)
        else:
            return default
    return d if d is not None else default


def parse_resume_for_llm(resume_json: dict) -> str:
    if not isinstance(resume_json, dict):
        return "Ошибка: входные данные не являются словарём."

    lines = []

    # === 1. Основная информация ===
    lines.append("## Основная информация:")
    title = safe_get(resume_json, "title") or "Не указано"
    lines.append(f"- Должность: {title}")

    gender = safe_get(resume_json, "gender", "name") or "Не указан"
    lines.append(f"- Пол: {gender}")

    age = safe_get(resume_json, "age")
    lines.append(f"- Возраст: {age} лет" if age is not None else "- Возраст: не указан")

    citizenship_list = safe_get(resume_json, "citizenship") or []
    citizenship = ", ".join(c.get("name") for c in citizenship_list if isinstance(c, dict) and c.get("name")) or "Не указано"
    lines.append(f"- Гражданство: {citizenship}")

    work_ticket_list = safe_get(resume_json, "work_ticket") or []
    work_ticket = ", ".join(w.get("name") for w in work_ticket_list if isinstance(w, dict) and w.get("name")) or "Не указано"
    lines.append(f"- РВП / разрешение на работу: {work_ticket}")

    has_vehicle = resume_json.get("has_vehicle")
    lines.append(f"- Наличие автомобиля: {'Да' if has_vehicle else 'Нет'}")

    driver_licenses = safe_get(resume_json, "driver_license_types") or []
    license_ids = [d.get("id") for d in driver_licenses if isinstance(d, dict) and d.get("id")]
    driver_license_str = ", ".join(license_ids) if license_ids else "Не указаны"
    lines.append(f"- Категории водительских прав: {driver_license_str}")

    # === 2. Ожидания по работе ===
    lines.append("\n## Ожидания по работе:")

    salary = safe_get(resume_json, "salary")
    if salary and isinstance(salary, dict):
        amount = salary.get("amount")
        currency = salary.get("currency", "RUB")
        lines.append(f"- Ожидаемая зарплата: {amount} {currency}" if amount else "- Ожидаемая зарплата: не указана")
    else:
        lines.append("- Ожидаемая зарплата: не указана")

    employments = safe_get(resume_json, "employments") or []
    employment = ", ".join(e.get("name") for e in employments if isinstance(e, dict) and e.get("name")) or "Не указано"
    lines.append(f"- Тип занятости: {employment}")

    employment_forms = safe_get(resume_json, "employment_form") or []
    employment_form = ", ".join(e.get("name") for e in employment_forms if isinstance(e, dict) and e.get("name")) or "Не указано"
    lines.append(f"- Форма занятости: {employment_form}")

    schedules = safe_get(resume_json, "schedules") or []
    schedules_str = ", ".join(s.get("name") for s in schedules if isinstance(s, dict) and s.get("name")) or "Не указано"
    lines.append(f"- График работы: {schedules_str}")

    work_formats = safe_get(resume_json, "work_format") or []
    work_format = ", ".join(w.get("name") for w in work_formats if isinstance(w, dict) and w.get("name")) or "Не указано"
    lines.append(f"- Формат работы: {work_format}")

    business_trip = safe_get(resume_json, "business_trip_readiness", "name") or "Не указано"
    lines.append(f"- Готовность к командировкам: {business_trip}")

    relocation_type = safe_get(resume_json, "relocation", "type", "name") or "Не указано"
    lines.append(f"- Готовность к переезду: {relocation_type}")

    travel_time = safe_get(resume_json, "travel_time", "name") or "Не указано"
    lines.append(f"- Допустимое время в пути до работы: {travel_time}")

    # === 3. Опыт работы ===
    lines.append("\n## Опыт работы:")
    total_exp_months = safe_get(resume_json, "total_experience", "months") or 0
    years = total_exp_months // 12
    months = total_exp_months % 12
    lines.append(f"- Общий стаж: {years} лет {months} месяцев")

    experience_items = safe_get(resume_json, "experience") or []
    if experience_items and isinstance(experience_items, list):
        for exp in experience_items:
            if not isinstance(exp, dict):
                continue
            company = exp.get("company") or "Не указано"
            position = exp.get("position") or "Не указана"
            start = exp.get("start", "???")
            end = exp.get("end") or "по настоящее время"
            description = exp.get("description", "").strip() if isinstance(exp.get("description"), str) else ""
            lines.append(f"\n• {position} в {company} ({start} – {end})")
            if description:
                for line in description.split("\n"):
                    stripped = line.strip()
                    if stripped:
                        lines.append(f"  - {stripped}")
    else:
        lines.append("- Опыт работы не указан")

    # === 4. Образование ===
    lines.append("\n## Образование:")
    education_level = safe_get(resume_json, "education", "level", "name") or "Не указано"
    lines.append(f"- Уровень образования: {education_level}")

    primary_edu = safe_get(resume_json, "education", "primary") or []
    if isinstance(primary_edu, list):
        for edu in primary_edu:
            if not isinstance(edu, dict):
                continue
            parts = []
            name = edu.get("name")
            org = edu.get("organization")
            result = edu.get("result")
            year = edu.get("year")
            if name: parts.append(name)
            if org: parts.append(org)
            if result: parts.append(result)
            if year: parts.append(str(year))
            lines.append(f"  • {', '.join(parts)}" if parts else "  • [данные не заполнены]")
    else:
        lines.append("  - Основное образование не указано")

    additional_edu = safe_get(resume_json, "education", "additional") or []
    if isinstance(additional_edu, list) and additional_edu:
        lines.append("  - Дополнительное образование / курсы:")
        for course in additional_edu:
            if not isinstance(course, dict):
                continue
            parts = []
            name = course.get("name")
            org = course.get("organization")
            year = course.get("year")
            if name: parts.append(name)
            if org: parts.append(org)
            if year: parts.append(str(year))
            lines.append(f"    • {', '.join(parts)}")
    else:
        lines.append("  - Дополнительное образование не указано")

    # === 5. Навыки и компетенции ===
    lines.append("\n## Навыки и компетенции:")

    skill_set = safe_get(resume_json, "skill_set") or []
    if isinstance(skill_set, list):
        lines.append("- Ключевые навыки: " + ", ".join(str(s) for s in skill_set if s))
    else:
        lines.append("- Ключевые навыки не указаны")

    skills_text = safe_get(resume_json, "skills") or ""
    if isinstance(skills_text, str) and skills_text.strip():
        lines.append("- Описание навыков и личных качеств:")
        for line in skills_text.split("\n"):
            stripped = line.strip()
            if stripped:
                lines.append(f"  {stripped}")
    else:
        lines.append("- Описание навыков отсутствует")

    # === 6. Языки ===
    lines.append("\n## Языки:")
    languages = safe_get(resume_json, "language") or []
    if isinstance(languages, list):
        for lang in languages:
            if not isinstance(lang, dict):
                continue
            name = lang.get("name", "Неизвестный язык")
            level = safe_get(lang, "level", "name") or "Не указан"
            lines.append(f"- {name}: {level}")
    else:
        lines.append("- Языки не указаны")

    # === 7. Местоположение ===
    lines.append("\n## Местоположение:")
    area = safe_get(resume_json, "area", "name") or "Не указано"
    lines.append(f"- Город: {area}")

    # === 8. Профессиональные роли (HH) ===
    lines.append("\n## Профессиональные роли (по классификации HH):")
    prof_roles = safe_get(resume_json, "professional_roles") or []
    if isinstance(prof_roles, list):
        roles = [r.get("name") for r in prof_roles if isinstance(r, dict) and r.get("name")]
        lines.append("- " + ", ".join(roles) if roles else "- Не указаны")
    else:
        lines.append("- Не указаны")

    return "\n".join(lines)