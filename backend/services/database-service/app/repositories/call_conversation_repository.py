"""Persistence for CallConversation rows imported from T2 ATS."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.calls.phones import conversation_involves_allowed_phones, involved_phones_clause
from app.db.v1.enums import CallConversationStatus
from app.db.v1.models import CallConversation
from app.t2.mapping import transcript_from_payload


class CallConversationRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get(self, conversation_id: int) -> Optional[CallConversation]:
        return await self._db.get(CallConversation, conversation_id)

    async def get_by_filename(self, filename: str) -> Optional[CallConversation]:
        result = await self._db.execute(
            select(CallConversation).where(CallConversation.filename == filename)
        )
        return result.scalars().first()

    async def get_by_ats_id(self, ats_id: str) -> Optional[CallConversation]:
        result = await self._db.execute(
            select(CallConversation).where(CallConversation.ats_id == ats_id)
        )
        return result.scalars().first()

    async def get_existing_by_filenames(self, filenames: Sequence[str]) -> dict[str, CallConversation]:
        clean = [str(name).strip() for name in filenames or [] if str(name or "").strip()]
        if not clean:
            return {}
        result = await self._db.execute(
            select(CallConversation).where(CallConversation.filename.in_(clean))
        )
        rows = result.scalars().all()
        return {row.filename: row for row in rows if getattr(row, "filename", None)}

    async def list_recent(
        self,
        *,
        limit: int = 200,
        offset: int = 0,
        status: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Sequence[CallConversation]:
        stmt = select(CallConversation)
        if status:
            stmt = stmt.where(CallConversation.status == status)
        allow_clause = involved_phones_clause(
            CallConversation.caller_number,
            CallConversation.operator_number,
        )
        if allow_clause is not None:
            stmt = stmt.where(allow_clause)
        if phone:
            like = f"%{phone}%"
            stmt = stmt.where(
                or_(
                    CallConversation.caller_number.ilike(like),
                    CallConversation.operator_number.ilike(like),
                )
            )
        stmt = (
            stmt.order_by(CallConversation.call_start_time.desc().nullslast())
            .offset(offset)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def list_pending(self, *, limit: int = 8) -> Sequence[CallConversation]:
        stmt = select(CallConversation).where(
            CallConversation.status == CallConversationStatus.pending.value
        )
        allow_clause = involved_phones_clause(
            CallConversation.caller_number,
            CallConversation.operator_number,
        )
        if allow_clause is not None:
            stmt = stmt.where(allow_clause)
        stmt = stmt.order_by(CallConversation.id.asc()).limit(limit)
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def apply_whisper_result(
        self,
        conversation_id: int,
        *,
        status: str,
        description: str,
    ) -> bool:
        row = await self.get(conversation_id)
        if row is None:
            return False
        if row.status != CallConversationStatus.pending.value:
            return False
        if not conversation_involves_allowed_phones(row):
            return False
        row.status = status
        row.description = description
        await self._db.commit()
        await self._db.refresh(row)
        return True

    async def list_missing_transcript(
        self,
        *,
        limit: int = 12,
        scan_multiplier: int = 5,
        min_call_start_time: Optional[datetime] = None,
    ) -> Sequence[CallConversation]:
        scan_limit = max(limit * max(scan_multiplier, 1), limit)
        stmt = select(CallConversation).where(CallConversation.filename.is_not(None))
        if min_call_start_time is not None:
            stmt = stmt.where(CallConversation.call_start_time.is_not(None))
            stmt = stmt.where(CallConversation.call_start_time >= min_call_start_time)
        stmt = stmt.order_by(CallConversation.call_start_time.desc().nullslast(), CallConversation.id.desc()).limit(scan_limit)
        result = await self._db.execute(stmt)
        rows = result.scalars().all()
        out = []
        for row in rows:
            words = transcript_from_payload(getattr(row, "payload", None))
            if words:
                continue
            out.append(row)
            if len(out) >= limit:
                break
        return out

    async def list_missing_transcript_for_backfill(
        self,
        *,
        limit: int = 12,
        scan_multiplier: int = 5,
        min_call_start_time: Optional[datetime] = None,
    ) -> tuple[Sequence[CallConversation], int]:
        """Return rows to retry STT and count rows skipped by age cutoff."""
        scan_limit = max(limit * max(scan_multiplier, 1), limit)
        stmt = (
            select(CallConversation)
            .where(CallConversation.filename.is_not(None))
            .order_by(CallConversation.call_start_time.desc().nullslast(), CallConversation.id.desc())
            .limit(scan_limit)
        )
        result = await self._db.execute(stmt)
        rows = result.scalars().all()
        out = []
        skipped_old = 0
        for row in rows:
            words = transcript_from_payload(getattr(row, "payload", None))
            if words:
                continue
            call_start_time = getattr(row, "call_start_time", None)
            if min_call_start_time is not None and (
                call_start_time is None or call_start_time < min_call_start_time
            ):
                skipped_old += 1
                continue
            out.append(row)
            if len(out) >= limit:
                break
        return out, skipped_old

    async def update_transcript(self, conversation_id: int, transcript: list[dict]) -> bool:
        row = await self.get(conversation_id)
        if row is None:
            return False
        payload = row.payload if isinstance(row.payload, dict) else {}
        payload["transcript"] = transcript
        row.payload = payload
        flag_modified(row, "payload")
        await self._db.commit()
        await self._db.refresh(row)
        return True

    async def upsert_from_ats(self, record: dict, transcript: list[dict]) -> CallConversation:
        filename = record["filename"]
        ats_id = record.get("ats_id")
        row = await self.get_by_filename(filename)
        if row is None and ats_id:
            row = await self.get_by_ats_id(ats_id)

        payload = {
            "transcript": transcript,
            "ats": record.get("source") or {},
        }

        if row is None:
            row = CallConversation(
                ats_id=ats_id,
                filename=filename,
                description=None,
                payload=payload,
                call_start_time=record.get("call_start_time"),
                call_end_time=record.get("call_end_time"),
                caller_number=record.get("caller_number"),
                operator_number=record.get("operator_number"),
                duration=record.get("duration"),
                status=CallConversationStatus.pending.value,
                ats_status=record.get("ats_status"),
                direction=record.get("direction"),
                caller_name=record.get("caller_name"),
                operator_name=record.get("operator_name"),
            )
            self._db.add(row)
        else:
            row.filename = filename
            if ats_id:
                row.ats_id = ats_id
            row.payload = payload
            flag_modified(row, "payload")
            row.call_start_time = record.get("call_start_time") or row.call_start_time
            row.call_end_time = record.get("call_end_time") or row.call_end_time
            row.caller_number = record.get("caller_number") or row.caller_number
            row.operator_number = record.get("operator_number") or row.operator_number
            if record.get("duration") is not None:
                row.duration = record["duration"]
            row.ats_status = record.get("ats_status") or row.ats_status
            row.direction = record.get("direction") or row.direction
            row.caller_name = record.get("caller_name") or row.caller_name
            row.operator_name = record.get("operator_name") or row.operator_name
            # HR status + description are owned by a later Whisper job — do not reset.

        await self._db.commit()
        await self._db.refresh(row)
        return row
