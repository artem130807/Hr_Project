from datetime import datetime, timedelta, timezone
from typing import Annotated
import os

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import (
    INVITE_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    ERP_AUTH_ENABLED,
    ERP_JWT_SECRET,
    ERP_JWT_ALGORITHM,
)

from app.db.v1.enums import BotRoles
from app.db.v1.models import ServiceClient
from app.app_logging import logger


def _load_private_key():
    """
    Загружает RSA private key из env PRIVATE_KEY (PEM, с \\n разделителями).
    Если не задан — генерирует временный ключ (только для dev), при этом токены
    не переживут рестарт и не валидны между воркерами/репликами.
    """
    pem_env = os.getenv("PRIVATE_KEY")
    if pem_env:
        try:
            pem_bytes = pem_env.replace("\\n", "\n").encode("utf-8")
            return serialization.load_pem_private_key(pem_bytes, password=None)
        except Exception as e:
            logger.error(f"Failed to load PRIVATE_KEY from env: {e}; generating ephemeral key")
    logger.error(
        "PRIVATE_KEY is not set — generating ephemeral RSA key. "
        "Access JWTs become invalid after every pod restart/redeploy. "
        "Refresh tokens still renew the session, but set a stable PRIVATE_KEY "
        "in hr-app-secret (see .env.example) for production."
    )
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


_private_key_obj = _load_private_key()
_public_key = _private_key_obj.public_key()

oauth2_sheme = OAuth2PasswordBearer(tokenUrl=f'/v1/token/user')
pwd_context = CryptContext(schemes=['bcrypt'])

#HASH
def get_hash(secret: str):
    return pwd_context.hash(secret)

def verify_secret(secret: str, hashed_secret: str) -> bool:
    return pwd_context.verify(secret, hashed_secret)


#TOKENS FOR TELEGRAM
def encode_invite_token(role: BotRoles, 
                        id: int | None = None) -> str:
    """Creates JWT token for candidate to bot_user connection"""
    payload = {
        "role": role.value,
        "id": id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=INVITE_TOKEN_EXPIRE_MINUTES)
    }
    invite_token = jwt.encode(payload, _private_key_obj, algorithm=ALGORITHM)
    return invite_token


#AUTHORIZATION TOKENS
async def authenticate_service(client_id: str, 
                               client_secret: str,
                               db: AsyncSession) -> ServiceClient | None:
    query = select(ServiceClient).where(ServiceClient.client_id==client_id)
    result = await db.execute(query)
    service: ServiceClient | None = result.scalar_one_or_none()
    if not service:
        raise HTTPException(404, 'Service not found')
    if not verify_secret(client_secret, service.client_secret_hash):
        return None
    return service


def create_token(data: dict, expires_delta: int | None = None):
    payload = data.copy()
    if expires_delta:
        expires = datetime.now(timezone.utc) + timedelta(minutes=expires_delta)
    else:
        expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    # PyJWT expects NumericDate (unix seconds). Passing datetime works in many
    # versions, but an int is unambiguous across stacks and clock checks.
    payload.update({"exp": int(expires.timestamp())})
    encoded_jwt = jwt.encode(payload, _private_key_obj, algorithm=ALGORITHM)
    return encoded_jwt, expires


async def get_current_user(token: Annotated[str, Depends(oauth2_sheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
        )

    # 1) ERP user access tokens (HS256) when centralized auth is on
    if ERP_AUTH_ENABLED and ERP_JWT_SECRET:
        try:
            from app.erp.auth_bridge import normalize_erp_access_payload

            payload = jwt.decode(token, ERP_JWT_SECRET, algorithms=[ERP_JWT_ALGORITHM])
            if payload.get("sub") is None:
                raise credentials_exception
            return normalize_erp_access_payload(payload)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except jwt.InvalidTokenError:
            pass  # fall through to local RS256 (service / legacy user JWTs)

    # 2) Local RS256 (service clients + legacy local user sessions)
    try:
        payload = jwt.decode(token, _public_key, algorithms=[ALGORITHM])
        if payload.get("sub") is None:
            logger.error("Username is None")
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise credentials_exception

    return payload


async def verify_external_access(user: Annotated[str, Depends(get_current_user)]):
    return user
