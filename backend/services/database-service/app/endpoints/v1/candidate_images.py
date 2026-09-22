from fastapi import APIRouter, Depends, status, HTTPException, Query
from typing import Optional
from app.db.v1.models import CompanyCandidateImage, DepartmentCandidateImage
from app.schemas.v1.candidate_images import (
    CompanyCandidateImageRead, DepartmentCandidateImageRead, CompanyCandidateImageCreate, 
    DepartmentCandidateImageCreate, CompanyCandidateImageUpdate, DepartmentCandidateImageUpdate,
    DepartmentFilter
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.middleware import get_db

router = APIRouter()

@router.get('/candidate-image/company', response_model=Optional[CompanyCandidateImageRead], status_code=status.HTTP_200_OK)
async def get_company_candidate_image_endpoint(db: AsyncSession = Depends(get_db)):
    query = select(CompanyCandidateImage)
    result = await db.execute(query)
    image = result.scalars().first()
    return image


@router.post('/candidate-image/company', response_model=CompanyCandidateImageRead, status_code=status.HTTP_201_CREATED)
async def post_company_candidate_image_endpoint(data: CompanyCandidateImageCreate,
                                              db: AsyncSession = Depends(get_db)):
    image = CompanyCandidateImage(**data.model_dump())
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image


@router.patch('/candidate-image/company', response_model=CompanyCandidateImageRead, status_code=status.HTTP_200_OK)
async def put_company_candidate_image_endpoint(db: AsyncSession = Depends(get_db),
                                             update_data: CompanyCandidateImageUpdate = None):
    query = select(CompanyCandidateImage)
    result = await db.execute(query)
    image = result.scalars().first()
    if not image:
        raise HTTPException(404, 'Company candidate image not found')
    
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(image, field, value)
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image


@router.get('/candidate-images/department/list', response_model=list[DepartmentCandidateImageRead], status_code=status.HTTP_200_OK)
async def list_department_candidate_images_endpoint(db: AsyncSession = Depends(get_db)):
    query = select(DepartmentCandidateImage)
    result = await db.execute(query)
    images = result.scalars().all()
    return images


@router.get('/candidate-image/department', response_model=Optional[DepartmentCandidateImageRead], status_code=status.HTTP_200_OK)
async def get_department_candidate_image_endpoint(filter_data: DepartmentFilter = Query(),
                                                  db: AsyncSession = Depends(get_db)):
    query = select(DepartmentCandidateImage).where(
        DepartmentCandidateImage.department == filter_data.department
    )
    result = await db.execute(query)
    image = result.scalars().first()
    return image


@router.post('/candidate-image/department', response_model=DepartmentCandidateImageRead, status_code=status.HTTP_201_CREATED)
async def post_department_candidate_image_endpoint(data: DepartmentCandidateImageCreate,
                                                 db: AsyncSession = Depends(get_db)):
    query = select(DepartmentCandidateImage).where(
        DepartmentCandidateImage.department == data.department
    )
    result = await db.execute(query)
    image = result.scalars().first()
    if image:
        raise HTTPException(409, 'Candidate image for this department already exists')
    payload = data.to_orm_dict()
    if not payload.get("lead_id"):
        payload["lead_id"] = None
    image = DepartmentCandidateImage(**payload)
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image


@router.patch('/candidate-image/department', response_model=DepartmentCandidateImageRead, status_code=status.HTTP_200_OK)
async def put_department_candidate_image_endpoint(update_data: DepartmentCandidateImageUpdate,
                                                filter_data: DepartmentFilter = Query(),
                                                db: AsyncSession = Depends(get_db)):
    query = select(DepartmentCandidateImage).where(
        DepartmentCandidateImage.department == filter_data.department
    )
    result = await db.execute(query)
    image = result.scalars().first()
    if not image:
        raise HTTPException(404, 'Department candidate image not found')
    
    for field, value in update_data.to_orm_dict(exclude_unset=True).items():
        setattr(image, field, value)
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image