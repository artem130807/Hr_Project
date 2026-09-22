"""HTTP adapters for VacancyFilter — thin layer over VacancyFilterService."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.middleware import get_db
from app.repositories.vacancy_filter_repository import VacancyFilterRepository
from app.schemas.v1.vacancy_filters import (
    VacancyFilterCreate,
    VacancyFilterRead,
    VacancyFilterUpdate,
)
from app.schemas.v1.vacancies import ReadVacancy
from app.services.vacancy_filter_service import VacancyFilterService

router = APIRouter()


def get_vacancy_filter_service(
    db: AsyncSession = Depends(get_db),
) -> VacancyFilterService:
    return VacancyFilterService(VacancyFilterRepository(db))


@router.post(
    "/vacancy-filters",
    response_model=VacancyFilterRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_vacancy_filter(
    data: VacancyFilterCreate,
    service: VacancyFilterService = Depends(get_vacancy_filter_service),
):
    return await service.create(data)


@router.get("/vacancy-filters", response_model=list[VacancyFilterRead])
async def list_vacancy_filters(
    service: VacancyFilterService = Depends(get_vacancy_filter_service),
):
    return await service.list()


@router.get("/vacancy-filters/{filter_id}", response_model=VacancyFilterRead)
async def get_vacancy_filter(
    filter_id: int,
    service: VacancyFilterService = Depends(get_vacancy_filter_service),
):
    return await service.get(filter_id)


@router.patch("/vacancy-filters/{filter_id}", response_model=VacancyFilterRead)
async def update_vacancy_filter(
    filter_id: int,
    data: VacancyFilterUpdate,
    service: VacancyFilterService = Depends(get_vacancy_filter_service),
):
    return await service.update(filter_id, data)


@router.delete(
    "/vacancy-filters/{filter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_vacancy_filter(
    filter_id: int,
    service: VacancyFilterService = Depends(get_vacancy_filter_service),
):
    await service.delete(filter_id)
    return None


@router.put(
    "/vacancy/{vacancy_id}/filter/{filter_id}",
    response_model=ReadVacancy,
)
async def assign_filter_to_vacancy(
    vacancy_id: int,
    filter_id: int,
    service: VacancyFilterService = Depends(get_vacancy_filter_service),
):
    return await service.assign_to_vacancy(vacancy_id, filter_id)


@router.delete(
    "/vacancy/{vacancy_id}/filter",
    response_model=ReadVacancy,
)
async def unassign_filter_from_vacancy(
    vacancy_id: int,
    service: VacancyFilterService = Depends(get_vacancy_filter_service),
):
    return await service.unassign_from_vacancy(vacancy_id)


@router.post("/vacancy/{vacancy_id}/run-filter")
async def run_vacancy_filter_now(
    vacancy_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Immediately run VacancyFilter auto-reject for this vacancy's HH responses
    (unviewed / «Неразобранные»). Proxied to hh-service.
    """
    from fastapi import HTTPException

    from app.db.v1.models import Vacancy
    from app.endpoints.v1.vacancies import _proxy_hh_import

    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(404, f"Вакансия #{vacancy_id} не найдена")
    if not vacancy.hh_vacancy_id:
        raise HTTPException(
            400,
            "Вакансия не привязана к HH.ru — сначала опубликуйте или импортируйте её",
        )
    if not vacancy.filter_id:
        raise HTTPException(400, "К вакансии не привязан фильтр")

    return await _proxy_hh_import(
        "POST",
        f"hh/local-vacancies/{vacancy_id}/run-filter",
        timeout=90.0,
    )
