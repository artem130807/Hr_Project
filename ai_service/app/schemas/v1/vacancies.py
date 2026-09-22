from pydantic import BaseModel, ConfigDict, Field, field_validator


class VacancyDescriptionSalaryRequest(BaseModel):
    """HR → AI: facts of the vacancy as a single text block."""

    formatted_vacancy: str = Field(
        ...,
        min_length=20,
        max_length=20000,
        description="Structured vacancy facts from HR (title, tasks, region, experience, …)",
    )

    @field_validator("formatted_vacancy")
    @classmethod
    def strip_facts(cls, value: str) -> str:
        text = (value or "").strip()
        if len(text) < 20:
            raise ValueError("formatted_vacancy is too short")
        return text


class VacancyDescriptionSalaryCombineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    salary_from: float | None = None
    salary_to: float | None = None


VacancyDescriptionSalaryCombineRequest = VacancyDescriptionSalaryRequest


class VacancyDescriptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str


class VacancySalaryPreciseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    salary_from: float | None = None
    salary_to: float | None = None


class VacancyData(BaseModel):
    formatted_vacancy: str = Field(..., min_length=1, max_length=20000)

    @field_validator("formatted_vacancy")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return (value or "").strip()
