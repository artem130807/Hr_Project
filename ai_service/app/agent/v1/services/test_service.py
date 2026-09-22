from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.v1.ai_client import AIClient

from app.schemas.v1.tests import TestGenerateResponse


class TestAIService:
    __test__ = False  # prevent pytest collecting this service class

    def __init__(self, ai_client: AIClient):
        self.ai = ai_client

    async def generate_test(
        self,
        topic: str,
        formatted_vacancy: str,
    ) -> TestGenerateResponse:
        prompt = (
            "Представь, что ты специалист по найму в разных сферах."
            "Тебе нужно составить максимально эффективный тест на следующую тему:\n\n"
            f"{topic}\n\n"
            "Этот тест должен помогать оценить кандидата в контексте следующей вакансии:\n\n"
            f"{formatted_vacancy}\n\n"
            "Тест должен содержать от 1 до 10 вопросов."
            "Ответь JSON в следующем формате (не обязательно брать эти значения, это просто JSON-структура ответа):\n\n"
            """{
            "name": "Тест на стрессоустойчивость",
            "description": "Тест, предназначенный для выявления психотипа человека",
            "instruction": "Отвечайте на вопросы честно",
            "questions": [
                {
                "text": "Как бы вы поступили в этой ситуации?"
                }
            ]
            }"""
        )
        return await self.ai.generate(
            prompt=prompt,
            temperature=0.5,
            output_model=TestGenerateResponse,
        )
