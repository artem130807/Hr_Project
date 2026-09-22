from typing import Annotated, Optional
import os

import httpx
import jwt
from jwt import PyJWK
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, Header, HTTPException, status, Request

from app.config import ALGORITHM, JWKS_URL
from app.app_logging import logger

oauth2_sheme = OAuth2PasswordBearer(tokenUrl="/v1/token/user", auto_error=False)

_public_key = None
_DB_INTERNAL = (os.getenv("DB_SERVICE_INTERNAL") or "").rstrip("/")


def set_public_key(key) -> None:
    global _public_key
    _public_key = key


def _candidate_secrets() -> list[str]:
    """All non-empty shared-secret candidates (order = preference)."""
    raw = [
        os.getenv("INTERNAL_PROXY_SECRET"),
        os.getenv("HH_SERVICE_CLIENT_SECRET"),
        os.getenv("DB_CLIENT_SECRET"),
        os.getenv("INTERNAL_HH_PROXY_TOKEN"),
    ]
    out: list[str] = []
    for value in raw:
        if not value:
            continue
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


def _expected_internal_token() -> str | None:
    secrets = _candidate_secrets()
    return secrets[0] if secrets else None


def _internal_token_ok(provided: str | None) -> bool:
    if not provided:
        return False
    expected = set(_candidate_secrets())
    return provided in expected


async def refresh_public_key() -> bool:
    """Reload RSA public key from database-service JWKS."""
    if not JWKS_URL:
        logger.error("JWKS_URL is not configured")
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(JWKS_URL)
            resp.raise_for_status()
            jwks = resp.json()
        keys = jwks.get("keys") or []
        if not keys:
            logger.error("JWKS payload has no keys")
            return False
        set_public_key(PyJWK(keys[0]).key)
        logger.info("JWKS public key refreshed from %s", JWKS_URL)
        return True
    except Exception as e:
        logger.error("JWKS refresh failed: %s", e)
        return False


async def _verify_token_via_database(token: str) -> Optional[dict]:
    """Source-of-truth verification against database-service signing key."""
    if not _DB_INTERNAL:
        logger.error("DB_SERVICE_INTERNAL is not configured — cannot verify token via DB")
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{_DB_INTERNAL}/v1/token/verify",
                json={"token": token},
            )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and data.get("sub"):
                return data
            return None
        logger.warning("token/verify returned HTTP %s: %s", resp.status_code, resp.text[:300])
    except Exception as e:
        logger.error("token/verify request failed: %s", e)
    return None


def _decode_locally(token: str) -> dict:
    if _public_key is None:
        raise jwt.InvalidTokenError("public key is not loaded")
    payload = jwt.decode(token, _public_key, algorithms=[ALGORITHM])
    if payload.get("sub") is None:
        raise jwt.InvalidTokenError("token subject is missing")
    return payload


async def validate_bearer_token(token: str) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1) Ask database-service first (avoids stale/wrong JWKS on hh-service)
    verified = await _verify_token_via_database(token)
    if verified:
        return verified

    # 2) Local JWKS
    try:
        return _decode_locally(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        logger.warning("Local JWT validation failed — refreshing JWKS")

    # 3) Refresh JWKS and retry local decode
    if await refresh_public_key():
        try:
            return _decode_locally(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            logger.warning("JWT still invalid after JWKS refresh")

    logger.error("Token verification failed (DB verify + JWKS)")
    raise credentials_exception


async def get_current_user(token: Annotated[Optional[str], Depends(oauth2_sheme)]):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await validate_bearer_token(token)


async def verify_external_access(user: Annotated[dict, Depends(get_current_user)]):
    return user


async def verify_external_or_internal(
    request: Request,
    x_internal_token: Annotated[Optional[str], Header(alias="X-Internal-Token")] = None,
    token: Annotated[Optional[str], Depends(oauth2_sheme)] = None,
):
    """Accept either shared-secret internal proxy header or a Bearer JWT."""
    if _internal_token_ok(x_internal_token):
        return {"sub": "internal-proxy", "type": "service"}

    if x_internal_token and _candidate_secrets():
        logger.warning(
            "X-Internal-Token present but does not match any configured secret "
            "(INTERNAL_PROXY_SECRET / HH_SERVICE_CLIENT_SECRET / DB_CLIENT_SECRET)"
        )

    if token:
        return await validate_bearer_token(token)

    logger.error(
        "Vacancy auth failed: internal_token=%s expected_configured=%s bearer=%s path=%s",
        bool(x_internal_token),
        bool(_candidate_secrets()),
        bool(token),
        request.url.path,
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
