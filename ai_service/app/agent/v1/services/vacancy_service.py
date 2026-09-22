from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.agent.v1.ai_client import AIClient

from app.agent.v1.errors import AIGenerationError
from app.config import MIN_VACANCY_DESCRIPTION_CHARS
from app.schemas.v1.vacancies import (
    VacancyDescriptionResponse,
    VacancyDescriptionSalaryCombineResponse,
    VacancySalaryPreciseResponse,
)


def _to_salary_int(raw) -> Optional[int]:
    if raw is None:
        return None
    try:
        number = int(round(float(raw)))
    except (TypeError, ValueError):
        return None
    return max(0, number)


def normalize_description_salary(
    result: VacancyDescriptionSalaryCombineResponse,
) -> VacancyDescriptionSalaryCombineResponse:
    description = (result.description or "").strip()
    salary_from = _to_salary_int(result.salary_from)
    salary_to = _to_salary_int(result.salary_to)
    if salary_from is not None and salary_to is not None and salary_from > salary_to:
        salary_from, salary_to = salary_to, salary_from
    return VacancyDescriptionSalaryCombineResponse(
        description=description,
        salary_from=salary_from,
        salary_to=salary_to,
    )


class VacancyAIService:
    def __init__(self, ai_client: AIClient):
        self.ai = ai_client

    async def generate_description(self, vacancy_text: str) -> VacancyDescriptionResponse:
        prompt = (
            "Ты HR-ассистент. На основе следующих данных о вакансии создай "
            "чёткое, привлекательное, развёрнутое и профессиональное описание вакансии на русском языке, "
            "которое готово к публикации. Длина обязана быть более 200 символов (сделай хотя бы 500-1000):\n\n"
            f"{vacancy_text}"
        )
        return await self.ai.generate(
            prompt=prompt,
            output_model=VacancyDescriptionResponse,
            temperature=0.8,
        )

    async def precise_salary(self, vacancy_text: str) -> VacancySalaryPreciseResponse:
        prompt = (
            "Ты аналитик рынка труда. На основе этих данных о вакансии оцени "
            "актуальный диапазон зарплат в RUB/month, используя веб-информацию. "
            "Используй информацию об обязанностях, географическом расположении и другую доступную информацию."
            "Отвечай JSON с полями `salary_from` и `salary_to`.\n\n"
            "   - Если зарплата конкретная — оба значения одинаковые.\n"
            "   - Если не удалось точно определить — один из порогов может быть None.\n"
            f"{vacancy_text}"
        )
        return await self.ai.generate(
            prompt=prompt,
            output_model=VacancySalaryPreciseResponse,
            use_web_search=True,
            temperature=0.3,
        )

    async def combine_description_and_salary(
        self, vacancy_text: str
    ) -> VacancyDescriptionSalaryCombineResponse:
        """One synchronous OpenAI call: publish-ready description + RUB salary band."""
        facts = (vacancy_text or "").strip()
        if len(facts) < 20:
            raise ValueError("Недостаточно данных о вакансии для генерации")

        result = await self._generate_combine(facts, strict_length=False)
        result = normalize_description_salary(result)
        if len(result.description) < MIN_VACANCY_DESCRIPTION_CHARS:
            result = await self._generate_combine(facts, strict_length=True)
            result = normalize_description_salary(result)
        if len(result.description) < MIN_VACANCY_DESCRIPTION_CHARS:
            raise AIGenerationError(
                f"Описание короче {MIN_VACANCY_DESCRIPTION_CHARS} символов"
            )
        return result

    async def _generate_combine(
        self, vacancy_text: str, *, strict_length: bool
    ) -> VacancyDescriptionSalaryCombineResponse:
        length_rule = (
            f"Описание ОБЯЗАНО быть не короче {MIN_VACANCY_DESCRIPTION_CHARS} символов, "
            "цель 500–1000 символов, готово к публикации на HH.ru."
        )
        if strict_length:
            length_rule = (
                f"КРИТИЧНО: description должен содержать минимум {MIN_VACANCY_DESCRIPTION_CHARS} "
                "символов. Нельзя возвращать короткое описание."
            )
        prompt = (
            "Ты HR-ассистент и аналитик рынка труда в России.\n"
            "По фактам вакансии ниже верни JSON с полями description, salary_from, salary_to.\n"
            f"1. description — {length_rule} Пиши на русском, без markdown-заголовков.\n"
            "2. salary_from / salary_to — оценка рынка в RUB за месяц (числа, не строки).\n"
            "   Опирайся на должность, регион, опыт и обязанности. Не выдумывай экзотическую валюту.\n"
            "   Если вилка одна цифра — оба поля одинаковые. Если данных мало — одно из полей null.\n"
            "Не добавляй других ключей.\n\n"
            f"Факты вакансии:\n{vacancy_text}"
        )
        generated = await self.ai.generate(
            prompt=prompt,
            output_model=VacancyDescriptionSalaryCombineResponse,
            use_web_search=True,
            temperature=0.4 if strict_length else 0.6,
        )
        if not isinstance(generated, VacancyDescriptionSalaryCombineResponse):
            raise AIGenerationError("combine_description_and_salary returned empty result")
        return generated
