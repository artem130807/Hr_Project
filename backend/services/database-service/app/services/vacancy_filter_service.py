"""
Business logic for VacancyFilter.

Relationship:
- one VacancyFilter → many Vacancy
- one Vacancy → at most one VacancyFilter
"""
from __future__ import annotations

from fastapi import HTTPException, status

from app.db.v1.models import Vacancy, VacancyFilter
from app.repositories.vacancy_filter_repository import VacancyFilterRepository
from app.schemas.v1.vacancy_filters import (
    VacancyFilterCreate,
    VacancyFilterUpdate,
    filter_has_criteria,
)


class VacancyFilterService:
    def __init__(self, repo: VacancyFilterRepository):
        self._repo = repo

    async def create(self, data: VacancyFilterCreate) -> VacancyFilter:
        return await self._repo.create(**data.model_dump())

    async def get(self, filter_id: int) -> VacancyFilter:
        entity = await self._repo.get_by_id(filter_id)
        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vacancy filter {filter_id} not found",
            )
        return entity

    async def list(self) -> list[VacancyFilter]:
        return list(await self._repo.list_all())

    async def update(self, filter_id: int, data: VacancyFilterUpdate) -> VacancyFilter:
        entity = await self._repo.get_by_id(filter_id)
        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vacancy filter {filter_id} not found",
            )
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(entity, field, value)
        # Cross-field age check after merge
        age_from = entity.age_from
        age_to = entity.age_to
        if age_from is not None and age_to is not None and age_from > age_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="age_from must be <= age_to",
            )
        if not filter_has_criteria(
            city=getattr(entity, "city", None),
            age_from=age_from,
            age_to=age_to,
            experience=getattr(entity, "experience", None),
            work_format=getattr(entity, "work_format", None),
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Укажите хотя бы одно условие фильтра",
            )
        return await self._repo.save(entity)

    async def delete(self, filter_id: int) -> None:
        entity = await self._repo.get_by_id(filter_id)
        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vacancy filter {filter_id} not found",
            )
        await self._repo.detach_vacancies(filter_id)
        await self._repo.delete(filter_id)

    async def assign_to_vacancy(self, vacancy_id: int, filter_id: int) -> Vacancy:
        filt = await self._repo.get_by_id(filter_id)
        if filt is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vacancy filter {filter_id} not found",
            )
        vacancy = await self._repo.get_vacancy(vacancy_id)
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vacancy {vacancy_id} not found",
            )
        return await self._repo.set_vacancy_filter(vacancy, filter_id)

    async def unassign_from_vacancy(self, vacancy_id: int) -> Vacancy:
        vacancy = await self._repo.get_vacancy(vacancy_id)
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vacancy {vacancy_id} not found",
            )
        return await self._repo.set_vacancy_filter(vacancy, None)
