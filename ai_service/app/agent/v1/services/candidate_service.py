from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.v1.ai_client import AIClient

from app.schemas.v1.candidates import CandidateEvaluateResponse
from app.schemas.v1.resume import ResumeEvaluateResponse


class CandidateAIService:
    def __init__(self, ai_client: AIClient):
        self.ai = ai_client

    async def evaluate_candidate(
        self,
        candidate_text: str,
        vacancy_text: str,
        company_image: str,
        department_image: str,
    ) -> CandidateEvaluateResponse:
        prompt = (
            "Ты HR-ассистент. Оцени от 0 до 100, насколько кандидат подходит для данной вакансии.\n"
            "- Совпадения по синонимам: название должности в резюме кандидата\n"
            "- Опыт на релевантной должности: должность и сколько по времени\n"
            "- Основные задачи: обязанности в резюме кандидата\n"
            "- Соответствие портретам от собственника и руководителя отдела\n\n"
            f"Вакансия:\n{vacancy_text}\n\n"
            f"Кандидат:\n{candidate_text}\n\n"
            f"Портрет идеального кандидата от собственника компании:\n{company_image}\n\n"
            f"Портрет идеального кандидата от руководителя отдела:\n{department_image}"
        )
        return await self.ai.generate(
            prompt=prompt,
            temperature=0.5,
            output_model=CandidateEvaluateResponse,
        )

    async def evaluate_resume(
        self,
        resume_text: str,
        vacancy_text: str,
    ) -> ResumeEvaluateResponse:
        prompt = (
            "Ты опытный HR-ассистент. Оцени соответствие кандидата вакансии по следующим критериям:\n"
            "1. Ключевые навыки (совпадение с требованиями вакансии)\n"
            "2. Опыт работы (релевантность, стаж, должности)\n"
            "3. Образование (уровень и профиль)\n"
            "4. Сертификаты и курсы (если указаны)\n"
            "5. Достижения, релевантные вакансии\n"
            "6. Соответствие должности (аналогичный опыт)\n"
            "7. География/релокация (если важно)\n"
            "8. Языковые требования\n"
            "9. Мотивация и карьерные цели\n"
            "10. Софт-скиллы (если важны для роли)\n\n"
            "По каждому из критериев оцени соответствие от 0 до 10 баллов, "
            "в ответе укажи сумму баллов по всем критериям\n\n"
            f"Вакансия:\n{vacancy_text}\n\n"
            f"Кандидат:\n{resume_text}"
        )
        return await self.ai.generate(
            prompt=prompt,
            temperature=0.5,
            output_model=ResumeEvaluateResponse,
        )
