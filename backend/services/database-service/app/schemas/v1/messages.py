from datetime import date, datetime, time

from pydantic import BaseModel, Field


class NewVacancyData(BaseModel):
    candidate_id: int = Field(..., example=1)
    vacancy_id: int = Field(..., example=1)


class SendOfferData(BaseModel):
    candidate_id: int = Field(..., example=1)
    offer_text: str = Field(..., example="Приглашаем вас на эту должность с зарплатой 50.000р")
    include_documents_link: bool = False


class SendInterviewInviteData(BaseModel):
    candidate_id: int
    message: str
    hr_id: str | None = None
    interview_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    book_calendar: bool = True
    remind_candidate: bool = False
    remind_at: datetime | None = None
    reminder_message: str | None = None


class ExerciseData(BaseModel):
    candidate_id: int = Field(..., example=1)
    instruction_text: str = Field(..., example="Вам нужно сделать это, а потом то")
    minutes: int = Field(..., example=60)


class SendProfessionalTestData(BaseModel):
    candidate_id: int = Field(..., example=1)
    test_id: int = Field(..., example=2)
    message: str | None = Field(
        default=None,
        description="Optional custom text for HH chat message",
    )
