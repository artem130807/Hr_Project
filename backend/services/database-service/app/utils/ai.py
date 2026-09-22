from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.v1.models import (
    Candidate, CandidateVacancyRelation, CandidateTestResult, 
    CandidateQuestionAnswer, Vacancy, CompanyCandidateImage,
    DepartmentCandidateImage
)
from app.db.v1.enums import TestResultsType
from app.clients.api_client import APICLient


async def generate_candidate_summary(
    candidate_id: int,
    db: AsyncSession,
) -> str:
    """
    Собирает summary по кандидату в виде str
    """
    # Загружаем кандидата с базовыми связями
    result = await db.execute(
        select(Candidate)
        .options(
            selectinload(Candidate.children),
            selectinload(Candidate.bot_user),
            selectinload(Candidate.vacancies).selectinload(CandidateVacancyRelation.vacancy),
            selectinload(Candidate.question_answers).selectinload(CandidateQuestionAnswer.question),
            selectinload(Candidate.test_results).selectinload(CandidateTestResult.test),
            selectinload(Candidate.test_results).selectinload(CandidateTestResult.answers),
        )
        .where(Candidate.id == candidate_id)
    )
    candidate: Candidate | None = result.scalars().first()
    
    if not candidate:
        raise HTTPException(404, "Candidate not found")

    summary_parts = [
        f"Возраст: {candidate.age}",
        f"Пол: {candidate.gender}",
        f"Семейное положение: {candidate.marital_status}",
        f"Хобби: {', '.join(candidate.hobbies)}" if candidate.hobbies else None,
        f"Дети: {', '.join([child.full_name for child in candidate.children])}" if candidate.children else None,
        f"Личные качества: {candidate.personal_characteristics}" if candidate.personal_characteristics else None,
        f"Языки: {', '.join(candidate.languages)}" if candidate.languages else None,
        f"Опыт по релевантной позиции: {candidate.relevant_position_expirience}" if candidate.relevant_position_expirience else None,
        f"Опыт по конкретной позиции: {candidate.certain_position_expirience}" if candidate.certain_position_expirience else None,
        f"Общий опыт работы: {candidate.total_work_expirience}" if candidate.total_work_expirience else None,
        f"Другой опыт: {', '.join(candidate.other_work_expirience)}" if candidate.other_work_expirience else None,
        f"Средняя длительность работы: {candidate.average_service_length}" if candidate.average_service_length else None,
        f"Образование: {', '.join(candidate.education)}" if candidate.education else None,
        f"Hard skills: {', '.join(candidate.hard_skills)}" if candidate.hard_skills else None,
        f"Work programs: {', '.join(candidate.work_programs)}" if candidate.work_programs else None,
        f"Резюме обновлено: {candidate.resume_update_date}" if candidate.resume_update_date else None,
        f"Активный поиск: {candidate.active_search}" if candidate.active_search else None,
        f"Ожидания по зарплате: {candidate.salary_expectations}" if candidate.salary_expectations else None,
        f"Vacancies: {', '.join([v.vacancy.name for v in candidate.vacancies])}" if candidate.vacancies else None,
    ]

    # Тесты
    test_parts = []
    for tr in candidate.test_results:
        test = tr.test
        if test.results_type == TestResultsType.text:
            # вопрос-ответ тест
            for ans in tr.answers:
                question_text = ans.question.text if ans.question else "?"
                answer_text = ans.answer_text or "нет ответа"
                test_parts.append(f"Тест {test.name}: {question_text} -> {answer_text} (Score: {ans.answer_score})")
        elif test.results_type == TestResultsType.screenshot_text:
            # тест с URL — просто результат кандидата
            test_parts.append(f"Тест {test.name}: результат кандидата: {tr.score} (Score), комментарий: {tr.comment}")
        elif test.results_type == TestResultsType.external_processing_result:
            # внешний тест — пропускаем
            continue

    if test_parts:
        summary_parts.append("Тесты и ответы:\n" + "\n".join(test_parts))

    # Ответы на вопросы
    if candidate.question_answers:
        qa_parts = []
        for qa in candidate.question_answers:
            question_text = qa.question.text if qa.question else "?"
            answer_text = qa.answer_text or "нет ответа"
            qa_parts.append(f"{question_text} -> {answer_text} (Score: {qa.answer_score})")
        summary_parts.append("Ответы на вопросы:\n" + "\n".join(qa_parts))

    summary = "\n".join([p for p in summary_parts if p])

    return summary


async def generate_vacancy_description(
    vacancy_id: int,
    hh: APICLient,
    db: AsyncSession
) -> str:
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail='Vacancy not found')

    # Получаем текстовые значения справочников
    professional_roles = []
    for role_id in vacancy.professional_roles_id or []:
        role = await hh.get(f'/v1/professional_roles/{role_id}')
        if role:
            professional_roles.append(role.get('name'))

    area = None
    if vacancy.area_id:
        area_resp = await hh.get(f'/v1/areas/{vacancy.area_id}')
        area = area_resp.get('name') if area_resp else None

    schedule = None
    if vacancy.schedule_id:
        schedule_resp = await hh.get(f'/v1/schedule/{vacancy.schedule_id}')
        schedule = schedule_resp.get('name') if schedule_resp else None

    employment = None
    if vacancy.employment_id:
        employment_resp = await hh.get(f'/v1/employment/{vacancy.employment_id}')
        employment = employment_resp.get('name') if employment_resp else None

    experience = None
    if vacancy.total_work_expirience:
        experience_resp = await hh.get(f'/v1/experience/{vacancy.total_work_expirience.value}')
        experience = experience_resp.get('name') if experience_resp else None

    # Собираем текст вакансии
    parts = [
        f"Название вакансии: {vacancy.name}",
        f"Синонимы: {', '.join(vacancy.synonyms)}" if vacancy.synonyms else None,
        f"Отдел: {vacancy.department.value}" if vacancy.department else None,
        f"Основные задачи: {', '.join(vacancy.main_tasks)}" if vacancy.main_tasks else None,
        f"Второстепенные задачи: {', '.join(vacancy.secondary_tasks)}" if vacancy.secondary_tasks else None,
        f"Обязательные навыки: {', '.join(vacancy.required_hard_skills)}" if vacancy.required_hard_skills else None,
        f"Желательные навыки: {', '.join(vacancy.optional_hard_skills)}" if vacancy.optional_hard_skills else None,
        f"Профессиональные роли: {', '.join(professional_roles)}" if professional_roles else None,
        f"Регион: {area}" if area else None,
        f"График работы: {schedule}" if schedule else None,
        f"Тип занятости: {employment}" if employment else None,
        f"Личные качества: {vacancy.personal_characteristics}" if vacancy.personal_characteristics else None,
        f"Опыт на релевантной позиции: {vacancy.relevant_position_expirience}" if vacancy.relevant_position_expirience else None,
        f"Опыт на требующейся позиции: {vacancy.certain_position_expirience}" if vacancy.certain_position_expirience else None,
        f"Другой опыт работы: {', '.join(vacancy.other_work_expirience)}" if vacancy.other_work_expirience else None,
        f"Общий опыт работы: {experience}" if vacancy.total_work_expirience else None,
        f"Образование: {', '.join(vacancy.education)}" if vacancy.education else None,
        f"Языки: {', '.join(vacancy.languages)}" if vacancy.languages else None,
        f"Рабочие программы: {', '.join(vacancy.work_programs)}" if vacancy.work_programs else None,
        f"KPI/метрики: {', '.join(vacancy.kpi_metrics)}" if vacancy.kpi_metrics else None,
    ]

    # Убираем пустые значения и объединяем в текст
    vacancy_text = "\n".join([p for p in parts if p])
    return vacancy_text


async def get_company_candidate_image(
        db: AsyncSession
        ) -> str:
    result = await db.execute(
        select(CompanyCandidateImage)
    )
    image = result.scalars().one_or_none()
    if not image:
        raise HTTPException(404, 'Image not found')
    
    parts = []
    if image.soft_skills:
        parts.append(f"Soft skills: {image.soft_skills}")
    if image.red_flags:
        parts.append(f"Red flags: {image.red_flags}")
    if image.common_requirements:
        parts.append(f"Common requirements: {image.common_requirements}")

    summary = "\n".join(parts)

    return summary


async def get_department_candidate_image(
    department: str,
    db: AsyncSession
    ) -> str:
    result = await db.execute(
        select(DepartmentCandidateImage).where(
            DepartmentCandidateImage.department == department
        )
    )
    image = result.scalars().one_or_none()
    if not image:
        raise HTTPException(404, 'Image not found')

    parts = []
    if image.hard_skills:
        parts.append(f"Hard skills: {image.hard_skills}")
    if image.expirience:
        parts.append(f"Experience: {image.expirience}")
    if image.common_requirements:
        parts.append(f"Common requirements: {image.common_requirements}")

    summary = "\n".join(parts)

    return summary