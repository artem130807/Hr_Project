from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime


class Area(BaseModel):
    id: str = Field(..., description="ID региона публикации (например, '1' — Москва)")


class Salary(BaseModel):
    from_: Optional[int] = Field(None, alias="from", description="Минимальная зарплата")
    to: Optional[int] = Field(None, description="Максимальная зарплата")
    currency: Optional[str] = Field("RUR", description="Валюта: 'RUR', 'USD' и т. д.")
    gross: Optional[bool] = Field(False, description="True — до вычета налогов, False — на руки")

    class Config:
        populate_by_name = True


class IDRef(BaseModel):
    id: str = Field(..., description="Идентификатор справочного значения")


class Phone(BaseModel):
    country: str = Field(..., description="Код страны (например, '7')")
    city: str = Field(..., description="Код города (например, '495')")
    number: str = Field(..., description="Основной номер телефона без +7 и кода города")


class Contacts(BaseModel):
    name: str = Field(..., description="Имя контактного лица")
    email: Optional[EmailStr] = Field(None, description="Email для связи")
    phones: List[Phone] = Field(default_factory=list, description="Список телефонов")


class VacancyPropertyItem(BaseModel):
    property_type: str = Field(default="HH_STANDARD", description="Тип публикации на HH")


class VacancyProperties(BaseModel):
    properties: List[VacancyPropertyItem] = Field(
        default_factory=lambda: [VacancyPropertyItem(property_type="HH_STANDARD")]
    )


class VacancyCreate(BaseModel):
    name: str = Field(..., description="Название вакансии (например, 'Дворник')")
    area: Area
    salary: Optional[Salary] = None
    description: str = Field(..., min_length=200, description="Описание вакансии (>=200 символов)")
    employment: IDRef = Field(..., description="Тип занятости ('full', 'part', и т. д.)")
    schedule: IDRef = Field(..., description="График ('fullDay', 'remote', и т. д.)")
    experience: IDRef = Field(..., description="Опыт ('noExperience', 'between1And3', ...)")
    professional_roles: List[IDRef] = Field(..., description="Список проф. ролей (например, [{'id': '10'}])")
    vacancy_properties: VacancyProperties = Field(default_factory=VacancyProperties)
    type: IDRef = Field(..., description="Тип публикации ('open', 'anonymous', ...)")
    billing_type: IDRef = Field(..., description="Тип биллинга ('standard', 'premium', ...)")
    contacts: Contacts

    class Config:
        extra = "ignore"
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "name": "Дворник",
                "area": {"id": "1"},
                "salary": {"from": 23000, "to": 23000, "currency": "RUR", "gross": False},
                "description": "Длинное описание (200+ символов)...",
                "employment": {"id": "full"},
                "schedule": {"id": "fullDay"},
                "experience": {"id": "noExperience"},
                "professional_roles": [{"id": "10"}],
                "vacancy_properties": {"properties": [{"property_type": "HH_STANDARD"}]},
                "type": {"id": "open"},
                "billing_type": {"id": "standard"},
                "contacts": {
                    "name": "Иван Иванов",
                    "email": "test@example.com",
                    "phones": [{"country": "7", "city": "495", "number": "1234567"}],
                },
            }
        }
