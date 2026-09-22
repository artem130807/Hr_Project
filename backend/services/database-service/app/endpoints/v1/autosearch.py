from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update, exists, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.middleware import get_db
from app.db.v1.models import AutoSearch, ReviewedResume
from app.db.v1.enums import EvaluationStatus, ResumeSearchStatus
from app.schemas.v1.autosearch import SearchItemCreate, SearchItemRead, ReviewedResumeCreate, ReviewedResumeRead, ReviewedResumeUpdate, ResumeExists, SearchItemUpdate
from app.app_logging import logger


router = APIRouter()


#==================================================
#                  Autosearch
#==================================================
@router.get('/autosearch/active', response_model=list[SearchItemRead])
async def list_active_searches_endpoint(
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(AutoSearch).
        where(AutoSearch.active == True)
    )
    result = await db.execute(query)
    items = result.scalars().all()
    
    return items


@router.post('/autosearch', response_model=SearchItemRead)
async def create_search_endpoint(
    data: SearchItemCreate,
    db: AsyncSession = Depends(get_db)
):
    search = AutoSearch(**data.model_dump())
    db.add(search)
    await db.commit()
    await db.refresh(search)
    return search


@router.get('/autosearch/vacancy/{vacancy_id}', response_model=SearchItemRead)
async def get_autosearch_by_vacancy_endpoint(
    vacancy_id: int, 
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(AutoSearch).
        where(AutoSearch.vacancy_id == vacancy_id)
    )
    result = await db.execute(query)
    search = result.scalar_one_or_none()
    if not search:
        raise HTTPException(404, "Autosearch not found")
    return search


@router.post('/autosearch/{search_id}/sent/add')
async def add_found_candidate_endpoint(
    search_id: int, 
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        update(AutoSearch)
        .where(AutoSearch.id == search_id)
        .values(total_sent=AutoSearch.total_sent + 1)
        .returning(AutoSearch.id, AutoSearch.total_sent)
    )

    result = await db.execute(stmt)
    updated_row = result.fetchone()
    
    if not updated_row:
        raise HTTPException(status_code=404, detail="AutoSearch record not found")

    await db.commit()
    return {"id": updated_row.id, "found": updated_row.total_sent}


@router.post("/autosearch/{search_id}/activate", response_model=SearchItemRead)
async def activate_search_endpoint(
    search_id: int,
    db: AsyncSession = Depends(get_db)
):

    query = select(AutoSearch).where(AutoSearch.id == search_id)
    res = await db.execute(query)
    search = res.scalar_one_or_none()

    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    search.active = True
    await db.commit()
    await db.refresh(search)

    return search


@router.post("/autosearch/{search_id}/deactivate", response_model=SearchItemRead)
async def deactivate_search_endpoint(
    search_id: int,
    db: AsyncSession = Depends(get_db)
):

    query = select(AutoSearch).where(AutoSearch.id == search_id)
    res = await db.execute(query)
    search = res.scalar_one_or_none()

    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    search.active = False
    await db.commit()
    await db.refresh(search)

    return search


@router.patch('/autosearch/{search_id}', response_model=SearchItemRead)
async def update_autosearch_endpoint(
    search_id: int,
    data: SearchItemUpdate,
    db: AsyncSession = Depends(get_db)
):
    query = select(AutoSearch).where(AutoSearch.id == search_id)
    res = await db.execute(query)
    search = res.scalar_one_or_none()
    if not search:
        raise HTTPException(status_code=404, detail="Autosearch not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(search, key, value)
    await db.commit()
    await db.refresh(search)
    return search


#==================================================
#              Reviewed Resumes
#==================================================
@router.get('/reviewed-resumes', response_model=list[ReviewedResumeRead])
async def list_reviewed_resumes_endpoint(
    page: int = Query(0, ge=0),
    per_page: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    offset = page * per_page

    query = (
        select(ReviewedResume)
        .order_by(ReviewedResume.id.desc())
        .offset(offset)
        .limit(per_page)
    )

    result = await db.execute(query)
    items = result.scalars().all()

    return items


@router.get('/reviewed-resumes/exists', response_model=ResumeExists)
async def reviewed_resume_exists(
    resume_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    query = select(
        exists().where(ReviewedResume.resume_id == resume_id)
    )
    result = await db.execute(query)
    exists_flag = result.scalar()
    return {"exists": exists_flag}


@router.post('/reviewed-resumes', response_model=ReviewedResumeRead)
async def create_reviewed_resume_endpoint(
    data: ReviewedResumeCreate,
    db: AsyncSession = Depends(get_db)
):
    resume = ReviewedResume(**data.model_dump())
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


@router.patch('/reviewed-resumes/{resume_id}', response_model=ReviewedResumeRead)
async def update_reviewed_resume_endpoint(
    resume_id: int,
    data: ReviewedResumeUpdate,
    db: AsyncSession = Depends(get_db)
):
    query = select(ReviewedResume).where(ReviewedResume.id == resume_id)
    result = await db.execute(query)
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(404, "Reviewed resume not found")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(resume, key, value)
    
    await db.commit()
    await db.refresh(resume)
    return resume


@router.get('/reviewed-resumes/best', response_model=list[ReviewedResumeRead])
async def get_best_resumes_endpoint(
    auto_search_id: int = Query(..., description="ID автопоиска"),
    limit: int = Query(10, ge=1, le=100, description="Количество лучших резюме"),
    min_score: float = Query(None, ge=0, le=100, description="Минимальная оценка"),
    db: AsyncSession = Depends(get_db)
):
    """
    Возвращает лучшие резюме по оценке для указанного автопоиска.
    Сортирует по score DESC и фильтрует только успешно оцененные резюме со статусом pending.
    """
    query = (
        select(ReviewedResume)
        .where(
            ReviewedResume.auto_search_id == auto_search_id,
            ReviewedResume.evaluation_status == EvaluationStatus.evaluated,
            ReviewedResume.status == ResumeSearchStatus.pending,
            ReviewedResume.score.isnot(None)
        )
    )
    
    if min_score is not None:
        query = query.where(ReviewedResume.score >= min_score)
    
    query = (
        query
        .order_by(desc(ReviewedResume.score))
        .limit(limit)
    )
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    return items






