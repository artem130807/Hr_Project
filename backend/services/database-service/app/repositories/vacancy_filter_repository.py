"""Persistence for VacancyFilter and vacancy↔filter links."""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.v1.enums import WorkExpirience, WorkFormat
from app.db.v1.models import Vacancy, VacancyFilter


class VacancyFilterRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        city: Optional[str] = None,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        experience: Optional[WorkExpirience] = None,
        work_format: Optional[WorkFormat] = None,
    ) -> VacancyFilter:
        entity = VacancyFilter(
            city=city,
            age_from=age_from,
            age_to=age_to,
            experience=experience,
            work_format=work_format,
        )
        self._db.add(entity)
        await self._db.commit()
        await self._db.refresh(entity)
        return entity

    async def get_by_id(self, filter_id: int) -> Optional[VacancyFilter]:
        return await self._db.get(VacancyFilter, filter_id)

    async def list_all(self) -> Sequence[VacancyFilter]:
        result = await self._db.execute(
            select(VacancyFilter).order_by(VacancyFilter.id.desc())
        )
        return result.scalars().all()

    async def save(self, entity: VacancyFilter) -> VacancyFilter:
        await self._db.commit()
        await self._db.refresh(entity)
        return entity

    async def delete(self, filter_id: int) -> bool:
        entity = await self.get_by_id(filter_id)
        if entity is None:
            return False
        await self._db.delete(entity)
        await self._db.commit()
        return True

    async def count_vacancies_using(self, filter_id: int) -> int:
        result = await self._db.execute(
            select(func.count())
            .select_from(Vacancy)
            .where(Vacancy.filter_id == filter_id)
        )
        return int(result.scalar_one() or 0)

    async def detach_vacancies(self, filter_id: int) -> None:
        await self._db.execute(
            update(Vacancy)
            .where(Vacancy.filter_id == filter_id)
            .values(filter_id=None)
        )
        await self._db.commit()

    async def get_vacancy(self, vacancy_id: int) -> Optional[Vacancy]:
        return await self._db.get(Vacancy, vacancy_id)

    async def set_vacancy_filter(
        self,
        vacancy: Vacancy,
        filter_id: Optional[int],
    ) -> Vacancy:
        vacancy.filter_id = filter_id
        await self._db.commit()
        await self._db.refresh(vacancy)
        return vacancy
