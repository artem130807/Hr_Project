"""Parse company contact phone strings into HH Phone parts."""
from __future__ import annotations

import re

from fastapi import HTTPException

from app.schemas.v1.vacancies import Contacts, Phone


def parse_phone_to_hh(raw: str) -> Phone | None:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    # Normalize leading 8 → 7 for RU
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits.startswith("7"):
        return Phone(country="7", city=digits[1:4], number=digits[4:])
    if len(digits) >= 10:
        return Phone(country="7", city=digits[-10:-7], number=digits[-7:])
    # Too short / incomplete — do not invent a city code
    return None


def contacts_from_company_contact(contact) -> Contacts:
    phones: list[Phone] = []
    for raw in contact.phone_number or []:
        p = parse_phone_to_hh(str(raw))
        if p:
            phones.append(p)
    if not phones:
        raise HTTPException(
            status_code=400,
            detail=(
                "У контактного лица компании нет корректного телефона для HH.ru. "
                "Добавьте номер в формате +7XXXXXXXXXX в разделе «Контакты»."
            ),
        )
    return Contacts(
        name=contact.name or "HR",
        email=contact.email,
        phones=phones,
    )
