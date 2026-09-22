"""Secure candidate-document invitations and private S3 object operations."""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from urllib.parse import quote, urlsplit, urlunsplit

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    CANDIDATE_DOCS_TOKEN_TTL_HOURS,
    CANDIDATE_DOCS_DRAFT_TTL_HOURS,
    S3_ACCESS_KEY_ID,
    S3_BUCKET,
    S3_ENDPOINT_URL,
    S3_PRESIGNED_TTL_SECONDS,
    S3_REGION,
    S3_SECRET_ACCESS_KEY,
)
from app.db.v1.models import (
    Candidate, CandidateDocs, CandidateDocumentInvite,
    CandidateDocumentUploadFile, CandidateDocumentUploadSession,
)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
ALLOWED_DOCUMENT_KINDS = {
    "passport",
    "snils",
    "inn",
    "marriage_certificate",
    "children_birth_certificate",
    "education",
    "employment_book",
    "military",
    "tachograph_card",
    "driver_license",
    "criminal_record_certificate",
    "medical_book",
    "other",
}
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_FILES = 20


def hash_token(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def build_public_url(request, token: str) -> str:
    configured = (os.getenv("HR_FRONTEND_BASE_URL") or os.getenv("FRONTEND_URL") or "").strip()
    if configured:
        parsed = urlsplit(configured.rstrip("/"))
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            path = parsed.path.rstrip("/")
            if path.endswith("/v1"):
                path = path[:-3]
            base = urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")
        else:
            base = ""
    else:
        base = ""
    if not base:
        base = (request.headers.get("Origin") or str(request.base_url)).rstrip("/")
    return f"{base}/candidate-documents/{quote(str(token), safe='')}"


async def create_invite(db: AsyncSession, candidate: Candidate, *, actor_id: str | None) -> tuple[CandidateDocumentInvite, str]:
    # Serialize invitation generation for one candidate so two simultaneous
    # offer actions cannot leave two usable public links behind.
    await db.execute(select(Candidate.id).where(Candidate.id == candidate.id).with_for_update())
    existing_docs = (await db.execute(select(CandidateDocs.id).where(CandidateDocs.candidate_id == candidate.id))).scalar_one_or_none()
    if existing_docs:
        raise HTTPException(409, "Кандидат уже отправил пакет документов")
    now = datetime.now(timezone.utc)
    active = (await db.execute(select(CandidateDocumentInvite).where(
        CandidateDocumentInvite.candidate_id == candidate.id,
        CandidateDocumentInvite.used_at.is_(None),
        CandidateDocumentInvite.revoked_at.is_(None),
    ))).scalars().all()
    for row in active:
        row.revoked_at = now
    # Release the partial unique index before inserting the replacement link.
    # Both flushes remain in the caller's transaction, so failures roll back
    # revocation as well as creation.
    if active:
        await db.flush()
    token = secrets.token_urlsafe(32)
    invite = CandidateDocumentInvite(
        candidate_id=candidate.id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(hours=CANDIDATE_DOCS_TOKEN_TTL_HOURS),
        created_by=actor_id,
    )
    db.add(invite)
    await db.flush()
    return invite, token


async def resolve_invite(db: AsyncSession, token: str, *, lock: bool = False, allow_used: bool = False) -> CandidateDocumentInvite:
    stmt = select(CandidateDocumentInvite).where(CandidateDocumentInvite.token_hash == hash_token(token))
    if lock:
        stmt = stmt.with_for_update()
    invite = (await db.execute(stmt)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    expires = invite.expires_at if invite else None
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not invite or invite.revoked_at or (invite.used_at and not allow_used) or not expires or expires <= now:
        raise HTTPException(404, "Ссылка недействительна или срок её действия истёк")
    return invite


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def create_upload_session(
    db: AsyncSession, invite: CandidateDocumentInvite
) -> tuple[CandidateDocumentUploadSession, str]:
    token = secrets.token_urlsafe(32)
    row = CandidateDocumentUploadSession(
        session_id=secrets.token_hex(16),
        token_hash=hash_token(token),
        invite_id=invite.id,
        candidate_id=invite.candidate_id,
        status="draft",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=CANDIDATE_DOCS_DRAFT_TTL_HOURS),
    )
    db.add(row)
    await db.flush()
    return row, token


async def resolve_upload_session(
    db: AsyncSession,
    invite: CandidateDocumentInvite,
    token: str,
    *,
    lock: bool = False,
    allow_submitted: bool = False,
) -> CandidateDocumentUploadSession:
    stmt = select(CandidateDocumentUploadSession).where(
        CandidateDocumentUploadSession.token_hash == hash_token(token),
        CandidateDocumentUploadSession.invite_id == invite.id,
        CandidateDocumentUploadSession.candidate_id == invite.candidate_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    allowed_statuses = {"draft", "submitted"} if allow_submitted else {"draft"}
    if not row or row.status not in allowed_statuses or _aware(row.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(404, "Черновик загрузки не найден или срок его действия истёк")
    return row


def _s3_client():
    if not S3_BUCKET or not S3_ACCESS_KEY_ID or not S3_SECRET_ACCESS_KEY:
        raise HTTPException(503, "Хранилище документов не настроено")
    try:
        import boto3
    except ImportError as exc:
        raise HTTPException(503, "S3-клиент не установлен") from exc
    return boto3.client(
        "s3", endpoint_url=S3_ENDPOINT_URL, region_name=S3_REGION,
        aws_access_key_id=S3_ACCESS_KEY_ID, aws_secret_access_key=S3_SECRET_ACCESS_KEY,
    )


def safe_filename(filename: str, index: int, content_type: str) -> str:
    raw = PurePosixPath(str(filename or "document").replace("\\", "/")).name
    stem = re.sub(r"[^a-zA-Z0-9а-яА-Я_-]+", "-", PurePosixPath(raw).stem).strip("-")[:80] or "document"
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}[content_type]
    return f"{index:02d}-{stem}{suffix}"


@dataclass(frozen=True)
class PreparedUpload:
    key: str
    kind: str
    filename: str
    content_type: str
    data: bytes


async def prepare_uploads(files: list[UploadFile], kinds: list[str], prefix: str) -> list[PreparedUpload]:
    if not files or len(files) > MAX_FILES or len(files) != len(kinds):
        raise HTTPException(422, "Передайте от 1 до 20 документов с типом для каждого файла")
    prepared: list[PreparedUpload] = []
    total = 0
    for index, (upload, raw_kind) in enumerate(zip(files, kinds), start=1):
        content_type = (upload.content_type or "").lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(415, "Разрешены JPG, PNG, WEBP и PDF")
        data = await upload.read(MAX_FILE_BYTES + 1)
        if not data:
            raise HTTPException(422, "Пустой файл нельзя загрузить")
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, "Размер одного документа не должен превышать 10 МБ")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(413, "Общий размер пакета не должен превышать 50 МБ")
        signatures = {
            "image/jpeg": data.startswith(b"\xff\xd8\xff"),
            "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP",
            "application/pdf": data.startswith(b"%PDF-"),
        }
        if not signatures.get(content_type, False):
            raise HTTPException(415, "Содержимое файла не соответствует его формату")
        kind = str(raw_kind).strip().lower()
        if kind not in ALLOWED_DOCUMENT_KINDS:
            raise HTTPException(422, "Неизвестный тип документа")
        filename = safe_filename(upload.filename or "document", index, content_type)
        prepared.append(PreparedUpload(f"{prefix}{kind}/{filename}", kind, filename, content_type, data))
    return prepared


async def upload_package(prepared: list[PreparedUpload]) -> list[dict]:
    client = _s3_client()
    uploaded: list[str] = []
    try:
        for item in prepared:
            await asyncio.to_thread(client.put_object, Bucket=S3_BUCKET, Key=item.key, Body=item.data, ContentType=item.content_type)
            uploaded.append(item.key)
    except Exception as exc:
        for key in uploaded:
            try:
                await asyncio.to_thread(client.delete_object, Bucket=S3_BUCKET, Key=key)
            except Exception:
                pass
        raise HTTPException(502, "Не удалось сохранить документы. Повторите попытку") from exc
    return [{"key": item.key, "kind": item.kind, "filename": item.filename, "content_type": item.content_type, "size": len(item.data)} for item in prepared]


async def upload_draft_file(item: PreparedUpload) -> dict:
    client = _s3_client()
    try:
        await asyncio.to_thread(
            client.put_object, Bucket=S3_BUCKET, Key=item.key, Body=item.data,
            ContentType=item.content_type, Tagging="status=draft"
        )
    except Exception as exc:
        raise HTTPException(502, "Не удалось сохранить документ. Повторите попытку") from exc
    return {"key": item.key, "kind": item.kind, "filename": item.filename,
            "content_type": item.content_type, "size": len(item.data)}


async def move_draft_package(files: list[CandidateDocumentUploadFile], candidate_id: int, session_id: str) -> list[dict]:
    """Copy draft objects to a durable prefix. Caller deletes copies if DB commit fails."""
    client = _s3_client()
    manifest: list[dict] = []
    try:
        for row in files:
            suffix = PurePosixPath(row.s3_key).suffix
            target = f"candidate-docs/{candidate_id}/submitted/{session_id}/{row.document_type}/{row.file_id}{suffix}"
            await asyncio.to_thread(
                client.copy_object,
                Bucket=S3_BUCKET,
                CopySource={"Bucket": S3_BUCKET, "Key": row.s3_key},
                Key=target,
                ContentType=row.content_type,
                MetadataDirective="REPLACE",
                Tagging="status=submitted",
                TaggingDirective="REPLACE",
            )
            manifest.append({"key": target, "kind": row.document_type, "filename": row.filename,
                             "content_type": row.content_type, "size": row.size})
    except Exception as exc:
        await delete_objects(manifest)
        raise HTTPException(502, "Не удалось подготовить пакет документов. Повторите попытку") from exc
    return manifest


async def delete_objects(manifest: list[dict]) -> bool:
    if not manifest:
        return True
    try:
        client = _s3_client()
    except Exception:
        return False
    success = True
    for item in manifest:
        try:
            await asyncio.to_thread(client.delete_object, Bucket=S3_BUCKET, Key=item["key"])
        except Exception:
            success = False
    return success


async def purge_expired_upload_sessions(db: AsyncSession, *, batch_size: int = 100) -> int:
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    now = datetime.now(timezone.utc)
    sessions = list((await db.execute(
        select(CandidateDocumentUploadSession).where(
            CandidateDocumentUploadSession.status == "draft",
            CandidateDocumentUploadSession.expires_at <= now,
        ).order_by(CandidateDocumentUploadSession.expires_at, CandidateDocumentUploadSession.id)
        .limit(batch_size).with_for_update(skip_locked=True)
    )).scalars().all())
    if not sessions:
        return 0
    purged = 0
    for session in sessions:
        files = list((await db.execute(select(CandidateDocumentUploadFile).where(
            CandidateDocumentUploadFile.session_id == session.id
        ))).scalars().all())
        if await delete_objects([{"key": row.s3_key} for row in files]):
            session.status = "expired"
            purged += 1
    await db.commit()
    return purged


async def presigned_manifest(manifest: list[dict]) -> list[dict]:
    if not manifest:
        return []
    client = _s3_client()
    result = []
    for item in manifest or []:
        url = await asyncio.to_thread(
            client.generate_presigned_url, "get_object",
            Params={"Bucket": S3_BUCKET, "Key": item["key"]}, ExpiresIn=S3_PRESIGNED_TTL_SECONDS,
        )
        result.append({**item, "url": url})
    return result
