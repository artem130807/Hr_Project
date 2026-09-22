"""HR API for T2-imported call conversations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.calls.phones import call_involves_allowed_phones
from app.db.middleware import get_db
from app.repositories.call_conversation_repository import CallConversationRepository
from app.schemas.v1.call_conversations import CallConversationRead

router = APIRouter()


def get_call_conversation_repository(
    db: AsyncSession = Depends(get_db),
) -> CallConversationRepository:
    return CallConversationRepository(db)


@router.get("/call-conversations", response_model=list[CallConversationRead])
async def list_call_conversations(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    repo: CallConversationRepository = Depends(get_call_conversation_repository),
) -> list[CallConversationRead]:
    rows = await repo.list_recent(limit=limit, offset=offset, status=status_filter)
    return [CallConversationRead.from_row(row) for row in rows]


@router.get("/call-conversations/{conversation_id}", response_model=CallConversationRead)
async def get_call_conversation(
    conversation_id: int,
    repo: CallConversationRepository = Depends(get_call_conversation_repository),
) -> CallConversationRead:
    row = await repo.get(conversation_id)
    if row is None or not call_involves_allowed_phones(row.caller_number, row.operator_number):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call conversation not found")
    return CallConversationRead.from_row(row)
