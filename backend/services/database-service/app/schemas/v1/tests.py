from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from pydantic.networks import AnyUrl
from app.db.v1.enums import TestType, TestResultsType


class BaseTestQuestion(BaseModel):
    text: str = Field(..., example='Как ы вы поступили в этой ситуации?')
    options: Optional[list[str]] = Field(default=None, example=["Вариант А", "Вариант Б"])
    correct_option_index: Optional[int] = Field(
        default=None,
        ge=0,
        example=0,
        description="Index of correct option in options (professional MCQ)",
    )


class TestQuestionCreate(BaseTestQuestion):
    pass


class TestQuestionRead(BaseTestQuestion):
    test_id: int = Field(..., example=1)
    id: int = Field(..., example=1)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BaseTest(BaseModel):
    name: str = Field(..., example='Иванов Иван Иванович')
    test_type: TestType = Field(..., example=TestType.url.value)
    results_type: TestResultsType = Field(..., example=TestResultsType.screenshot_text.value)

    url: str | None = Field(..., example='https://ttisi.ru/testdisc')

    description: str | None = Field(..., example='Пройдите тест на психотип')
    instruction_text: str = Field(..., example='Пройдите тест по ссылке и направьте ответным сообщением в бот текстовый результат со скриншотом')
    duration_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        le=600,
        example=30,
        description="Time limit for professional Q&A public take (minutes)",
    )


class TestCreate(BaseTest):
    pass


class TestUpdate(BaseModel):
    name: Optional[str] = None
    test_type: Optional[TestType] = None
    results_type: Optional[TestResultsType] = None
    url: Optional[str] = None
    description: Optional[str] = None
    instruction_text: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=600)


class TestReadWOQuestions(BaseTest):
    id: int = Field(..., example=1)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestRead(BaseTest):
    id: int = Field(..., example=1)
    questions: Optional[list[TestQuestionRead]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BaseCandidateTestResult(BaseModel):
    candidate_id: int = Field(..., example=1)
    test_id: int = Field(..., example=1)
    has_image: bool = Field(default=False, example=False)
    score: Optional[int] = Field(example=78)
    comment: Optional[str] = Field(example='Кандидат крутой')


class CandidatTestResultCreate(BaseCandidateTestResult):
    pass


class CandidateQuestionAnswerRead(BaseModel):
    id: int = Field(..., example=1)
    candidate_id: int = Field(..., example=1)
    question_id: int = Field(..., example=1)
    result_id: Optional[int] = Field(default=None, example=1)
    answer_text: Optional[str] = Field(default=None, example="Ответ кандидата")
    answer_score: Optional[int] = Field(default=None, example=5)
    question: Optional[TestQuestionRead]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CandidateQuestionAnswerBase(BaseModel):
    candidate_id: int = Field(..., example=1)
    question_id: int = Field(..., example=1)
    result_id: Optional[int] = Field(default=None, example=1)
    answer_text: Optional[str] = Field(default=None, example="Ответ кандидата")
    answer_score: Optional[int] = Field(default=None, example=5)


class CandidateQuestionAnswerCreate(CandidateQuestionAnswerBase):
    pass


class CandidateQuestionAnswerUpdate(BaseModel):
    result_id: Optional[int] = Field(default=None, example=1)
    answer_text: Optional[str] = Field(default=None, example="Ответ кандидата")
    answer_score: Optional[int] = Field(default=None, example=5)


class CandidatTestResultRead(BaseCandidateTestResult):
    id: int = Field(..., example=1)
    answers: list[CandidateQuestionAnswerRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, **kwargs):
        instance = super().model_validate(obj, **kwargs)
        instance.has_image = obj.has_image or (obj.image_data is not None)
        return instance
