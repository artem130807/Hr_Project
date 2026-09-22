from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.schemas.v1.contacts import CreateContact, ReadContact, UpdateContact
from app.db.v1.models import CompanyContact
from app.db.middleware import get_db
from app.utils.hh_contacts import parse_phone_to_hh

router = APIRouter()


def _require_valid_phones(phones: list[str] | None) -> list[str]:
    cleaned = [str(p).strip() for p in (phones or []) if str(p).strip()]
    if not cleaned:
        raise HTTPException(
            status_code=400,
            detail="Укажите хотя бы один телефон в формате +7XXXXXXXXXX",
        )
    valid = [p for p in cleaned if parse_phone_to_hh(p)]
    if not valid:
        raise HTTPException(
            status_code=400,
            detail="Некорректный телефон. Используйте формат +7XXXXXXXXXX",
        )
    if len(valid) != len(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Все телефоны должны быть в формате +7XXXXXXXXXX",
        )
    return valid


@router.post("/company_contacts", response_model=ReadContact, status_code=status.HTTP_201_CREATED)
async def create_company_contact(
    contact: CreateContact,
    db: AsyncSession = Depends(get_db)
):
    """Создание контактного лица компании."""
    payload = contact.model_dump()
    payload["phone_number"] = _require_valid_phones(payload.get("phone_number"))
    new_contact = CompanyContact(**payload)
    db.add(new_contact)
    await db.commit()
    await db.refresh(new_contact)
    return new_contact


@router.get("/company_contacts", response_model=list[ReadContact])
async def list_company_contacts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    """Получение списка контактных лиц компании с пагинацией."""
    result = await db.execute(
        select(CompanyContact).order_by(CompanyContact.id.asc()).offset(skip).limit(limit)
    )
    contacts = result.scalars().all()
    return contacts


# Static path must be registered before /{contact_id}
@router.get('/company_contacts/hr/{hr_id}', response_model=ReadContact)
async def get_contact_by_hr_id(
    hr_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Получение контактного лица компании по ID HR менеджера."""
    result = await db.execute(
        select(CompanyContact).where(CompanyContact.hr_id == hr_id)
    )
    contact = result.scalars().first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return contact


@router.get("/company_contacts/{contact_id}", response_model=ReadContact)
async def get_company_contact(
    contact_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получение контактного лица компании по ID."""
    result = await db.get(CompanyContact, contact_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return result


@router.delete("/company_contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_contact(
    contact_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Удаление контактного лица компании по ID."""
    contact = await db.get(CompanyContact, contact_id)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    await db.delete(contact)
    await db.commit()
    return


@router.put("/company_contacts/{contact_id}", response_model=ReadContact)
async def update_company_contact(
    contact_id: int,
    contact_update: UpdateContact,
    db: AsyncSession = Depends(get_db)
):
    """Обновление контактного лица компании по ID."""
    contact = await db.get(CompanyContact, contact_id)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    updates = contact_update.model_dump(exclude_unset=True)
    if "phone_number" in updates:
        updates["phone_number"] = _require_valid_phones(updates.get("phone_number"))

    for key, value in updates.items():
        setattr(contact, key, value)

    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact
