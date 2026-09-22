from pydantic import BaseModel, Field, RootModel
from typing import List, Optional


# ======================
# Основные справочники
# ======================

class Area(BaseModel):
    id: str = Field(example="1")
    parent_id: Optional[str] = Field(example="113")
    name: str = Field(example="Москва")
    areas: List["Area"] = Field(default_factory=list)

Area.model_rebuild()


class ProfessionalRole(BaseModel):
    id: str = Field(example="59")
    name: str = Field(example="Менеджер по продажам")


class ProfessionalRoleGroup(BaseModel):
    id: str = Field(example="1")
    name: str = Field(example="Информационные технологии")
    roles: List[ProfessionalRole] = Field(default_factory=list)


class ProfessionalRolesResponse(BaseModel):
    categories: List[ProfessionalRoleGroup]


class Language(BaseModel):
    id: str = Field(example="eng")
    name: str = Field(example="Английский")


class Currency(BaseModel):
    abbr: str = Field(example="RUR")
    name: str = Field(example="Российский рубль")
    default: bool = Field(example=True)
    rate: float = Field(example=1.0)
    in_use: bool = Field(example=True)


# ======================
# Справочники из /dictionaries
# ======================

class DictionaryItem(BaseModel):
    id: str
    name: str


class ExperienceItem(DictionaryItem):
    id: str = Field(example="between1And3")
    name: str = Field(example="От 1 года до 3 лет")


class EmploymentItem(DictionaryItem):
    id: str = Field(example="full")
    name: str = Field(example="Полная занятость")


class ScheduleItem(DictionaryItem):
    id: str = Field(example="remote")
    name: str = Field(example="Удаленная работа")


class EducationLevelItem(DictionaryItem):
    id: str = Field(example="higher")
    name: str = Field(example="Высшее")


class LanguageLevelItem(DictionaryItem):
    id: str = Field(example="b2")
    name: str = Field(example="B2 — Средне-продвинутый")


class DriverLicenseTypeItem(BaseModel):
    id: str = Field(example="B")


class WorkFormatItem(DictionaryItem):
    id: str = Field(example="REMOTE")
    name: str = Field(example="Удалённо")


class WorkingDaysItem(DictionaryItem):
    id: str = Field(example="only_saturday_and_sunday")
    name: str = Field(example="По субботам и воскресеньям")


class WorkingTimeIntervalsItem(DictionaryItem):
    id: str = Field(example="from_four_to_six_hours_in_a_day")
    name: str = Field(example="Можно сменами по 4-6 часов в день")


class WorkingTimeModesItem(DictionaryItem):
    id: str = Field(example="start_after_sixteen")
    name: str = Field(example="С начала дня после 16:00")


class WorkScheduleByDaysItem(DictionaryItem):
    id: str = Field(example="WEEKEND")
    name: str = Field(example="По выходным")


class WorkingHoursItem(DictionaryItem):
    id: str = Field(example="HOURS_8")
    name: str = Field(example="8 часов")


class AgeRestrictionItem(DictionaryItem):
    id: str = Field(example="AGE_14_PLUS")
    name: str = Field(example="От 14 лет")


class VacancyTypeItem(DictionaryItem):
    id: str = Field(example="open")
    name: str = Field(example="Открытая")


class BusinessTripReadinessItem(DictionaryItem):
    id: str = Field(example="ready")
    name: str = Field(example="Готов к командировкам")


class RelocationTypeItem(DictionaryItem):
    id: str = Field(example="relocation_possible")
    name: str = Field(example="Могу переехать")


class GenderItem(DictionaryItem):
    id: str = Field(example="male")
    name: str = Field(example="Мужской")


class ResumeAccessTypeItem(DictionaryItem):
    id: str = Field(example="everyone")
    name: str = Field(example="Видно всему интернету")
