"""Shared hiring-request creation and one-time public invitation helpers."""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlsplit, urlunsplit

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import HIRING_REQUEST_INVITE_TTL_HOURS
from app.db.v1.enums import HiringRequestStatus
from app.db.v1.models import EmployeeRequest, HiringRequestInvite
from app.events.publisher import publish_hr_hiring_request_created
from app.messaging.channel_events import publish_hiring_request_created, safe_channel_publish
from app.schemas.v1.hiring_request import EmployeeRequestCreate
from app.utils.audit import write_audit


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def public_hiring_request_url(request: Request, token: str) -> str:
    configured = (os.getenv("HR_FRONTEND_BASE_URL") or os.getenv("FRONTEND_URL") or "").strip()
    base = ""
    if configured:
        parsed = urlsplit(configured.rstrip("/"))
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            path = parsed.path.rstrip("/")
            if path.endswith("/v1"):
                path = path[:-3]
            base = urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")
    if not base:
        base = (request.headers.get("Origin") or str(request.base_url)).rstrip("/")
    return f"{base}/hiring-request/{quote(str(token), safe='')}"


async def create_invite(
    db: AsyncSession,
    *,
    actor_id: str | None,
    actor_name: str | None,
) -> tuple[HiringRequestInvite, str]:
    token = secrets.token_urlsafe(32)
    invite = HiringRequestInvite(
        token_hash=hash_invite_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=HIRING_REQUEST_INVITE_TTL_HOURS),
        created_by=actor_id,
        created_by_name=actor_name,
    )
    db.add(invite)
    await db.flush()
    return invite, token


async def resolve_invite(db: AsyncSession, token: str, *, lock: bool = False) -> HiringRequestInvite:
    stmt = select(HiringRequestInvite).where(HiringRequestInvite.token_hash == hash_invite_token(token))
    if lock:
        stmt = stmt.with_for_update()
    invite = (await db.execute(stmt)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    expires_at = invite.expires_at if invite else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not invite or invite.used_at or invite.revoked_at or not expires_at or expires_at <= now:
        raise HTTPException(404, "Ссылка недействительна, уже использована или срок её действия истёк")
    return invite


async def create_request_record(
    db: AsyncSession,
    data: EmployeeRequestCreate,
    *,
    audit_action: str = "hiring_request.create",
) -> EmployeeRequest:
    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    if not payload.get("initiator_name"):
        payload["initiator_name"] = payload.get("manager_name")
    payload["status"] = HiringRequestStatus.created
    payload["status_changed_at"] = datetime.now(timezone.utc)
    row = EmployeeRequest(**payload)
    db.add(row)
    await db.flush()
    await write_audit(
        db,
        action=audit_action,
        entity_type="hiring_request",
        entity_id=row.id,
        details=f"{row.position} / {row.department}",
    )
    return row


async def publish_request_created(
    row: EmployeeRequest,
    *,
    actor_id: str | None,
    actor_name: str | None,
) -> None:
    await safe_channel_publish(
        publish_hiring_request_created(row, actor_user_id=actor_id, actor_name=actor_name),
        context="hiring_request.create",
    )
    await safe_channel_publish(
        publish_hr_hiring_request_created(row, actor_user_id=actor_id, actor_name=actor_name),
        context="hr.hiring_request.create",
    )
