from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from app.api.enums import (
    BotRoles, TestType
)


class BaseBotUser(BaseModel):
    telegram_id: str = Field(..., example='1685316319')
    name: str = Field(..., example='istendlay')
    role: BotRoles = Field(..., example=BotRoles.candidate.value)

    class Config:
        use_enum_values = True


class BotUserCreate(BaseBotUser):
    candidate_id: Optional[int] = Field(default=None)
    employee_id: Optional[int] = Field(default=None)
    admin_id: Optional[int] = Field(default=None)


class BotUserRead(BaseBotUser):
    id: int = Field(..., example='1')
    # candidate_id: Optional[int] = Field(example=4)
    # employee_id: Optional[int] = Field(example=7)
    # admin_id: Optional[int] = Field(example=9)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BotUserDelete(BaseModel):
    id: int = Field(..., example='1')


class BotUserUpdate(BaseModel):
    telegram_id: Optional[str] = Field(None, example='1685316319')
    name: Optional[str] = Field(None, example='istendlay')
    role: Optional[BotRoles] = Field(None, example=BotRoles.candidate.value)
    candidate_profile_id: Optional[int] = Field(None, example=1)
    employee_profile_id: Optional[int] = Field(None, example=1)
    admin_profile_id: Optional[int] = Field(None, example=1)

    class Config:
        use_enum_values = True


class InviteTokenRead(BaseModel):
    token: str = Field(example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjYW5kaWRhdGVfaWQiOjEsImV4cCI6MTc1NjU2Mzc3OH0.T8qKNzlMTB1P75tBA5ZJWCX9EZ3H4o-KN2JdAfTx7l0")


class BaseProgress(BaseModel):
    vacancy_description: Optional[bool] = Field(default=False, example=True)
    company_info: Optional[bool] = Field(default=False, example=True)
    corp_culture: Optional[bool] = Field(default=False, example=False)
    my_resume: Optional[bool] = Field(default=False, example=True)
    agreement: Optional[bool] = Field(None, example=False)
    test_disc: Optional[bool] = Field(None, example=False)
    test_adizes: Optional[bool] = Field(None, example=False)


class UpdateProgress(BaseModel):
    vacancy_description: Optional[bool] = Field(None, example=False)
    company_info: Optional[bool] = Field(None, example=False)
    corp_culture: Optional[bool] = Field(None, example=False)
    my_resume: Optional[bool] = Field(None, example=False)
    agreement: Optional[bool] = Field(None, example=False)
    test_disc: Optional[bool] = Field(None, example=False)
    test_adizes: Optional[bool] = Field(None, example=False)


class ReadProgress(BaseProgress):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True




class BaseTestQuestion(BaseModel):
    text: str = Field(..., example='Как ы вы поступили в этой ситуации?')



class TestQuestionRead(BaseTestQuestion):
    test_id: int = Field(..., example=1)
    id: int = Field(..., example=1)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attrubutes = True


class BaseTest(BaseModel):
    name: str = Field(..., example='Иванов Иван Иванович')
    type: TestType = Field(..., example=TestType.url.value)

    url: str = Field(..., example='https://ttisi.ru/testdisc')

    description: str = Field(..., example='Пройдите тест по ссылке, результат отправьте ответным ссобщением в виде скриншота и текста')


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

    score: Optional[int] = Field(example=78)
    comment: Optional[str] = Field(example='Кандидат крутой')


class CandidateQuestionAnswerRead(BaseModel):
    id: int = Field(..., example=1)
    candidate_id: int = Field(..., example=1)
    question_id: int = Field(..., example=1)
    result_id: Optional[int] = Field(default=None, example=1)
    answer_text: Optional[str] = Field(default=None, example='Ответ кандидата')
    answer_score: Optional[int] = Field(default=None, example=5)
    question: Optional[TestQuestionRead]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CandidateQuestionAnswerCreate(BaseModel):
    candidate_id: int = Field(..., example=1)
    question_id: int = Field(..., example=1)
    result_id: Optional[int] = Field(default=None, example=1)
    answer_text: Optional[str] = Field(default=None, example='Ответ кандидата')
    answer_score: Optional[int] = Field(default=None, example=5)


class CandidateQuestionAnswerUpdate(BaseModel):
    result_id: Optional[int] = Field(default=None, example=1)
    answer_text: Optional[str] = Field(default=None, example='Ответ кандидата')
    answer_score: Optional[int] = Field(default=None, example=5)


class CandidatTestResultRead(BaseCandidateTestResult):
    id: int = Field(..., example=1)
    answers: list[CandidateQuestionAnswerRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
