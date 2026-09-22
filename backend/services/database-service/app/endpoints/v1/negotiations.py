from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.middleware import get_db

from app.db.v1.models import Negotiation, Candidate, CandidateVacancyRelation
from app.schemas.v1.negotiations import NegotiationCreate, NegotiationUpdate, NegotiationRead


router = APIRouter()


@router.post('/negotiation', response_model=NegotiationRead)
async def post_negotiation(
    data: NegotiationCreate,
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(CandidateVacancyRelation)
        .where(
            CandidateVacancyRelation.candidate_id == data.candidate_id,
             CandidateVacancyRelation.is_active == True
        )
    )
    result = await db.execute(query)
    rel = result.scalar_one_or_none()
    if not rel:
        raise HTTPException(409, 'No active vacancy for this candidate')
    
    negotiation = Negotiation(
        candidate_id = data.candidate_id,
        vacancy_id = rel.vacancy_id,
        read = False
    )
    db.add(negotiation)
    await db.commit()
    await db.refresh(negotiation)
    return negotiation
    

@router.post('/negotiation/read', response_model=NegotiationRead)
async def read_negotiation(
    data: NegotiationUpdate,
    db: AsyncSession = Depends(get_db)
):
    q = (
        select(Negotiation)
        .join(
            CandidateVacancyRelation,
            CandidateVacancyRelation.vacancy_id == Negotiation.vacancy_id
        )
        .where(
            Negotiation.candidate_id == data.candidate_id,
            CandidateVacancyRelation.candidate_id == data.candidate_id,
            CandidateVacancyRelation.is_active == True
        )
    )

    res = await db.execute(q)
    negotiation = res.scalars().one_or_none()
    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    negotiation.read = True
    await db.commit()
    await db.refresh(negotiation)
    return negotiation


@router.get('/negotiations/unread', response_model=list[NegotiationRead])
async def get_unread_negotiations_endpoint(
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Negotiation)
        .where(Negotiation.read == False)
    )
    result = await db.execute(query)
    negotiations = result.scalars().all()
    
    return negotiations