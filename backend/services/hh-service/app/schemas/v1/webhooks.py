from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


# --- Pydantic схемы для hh webhook ---
class ResumeShort(BaseModel):
    id: str
    first_name: Optional[str]
    last_name: Optional[str]
    title: Optional[str]
    area: Optional[Dict[str, Any]]
    url: Optional[str]
    # ...добавить нужные поля по необходимости

class VacancyShort(BaseModel):
    id: str
    name: Optional[str]
    area: Optional[Dict[str, Any]]
    url: Optional[str]
    # ...добавить нужные поля по необходимости

class NegotiationWebhookPayload(BaseModel):
    event: str = Field(..., description="Тип события, например 'new_negotiation'")
    negotiation: Dict[str, Any]
    # negotiation содержит id, state, resume, vacancy и др.