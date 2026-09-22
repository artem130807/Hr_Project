from typing import Annotated, Optional
import os

import httpx
import jwt
from jwt import PyJWK
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, Header, HTTPException, status

from app.app_logging import logger
from app.config import ALGORITHM, CLIENT_SECRET, DB_SERVICE_BASE_URL, JWKS_URL

oauth2_sheme = OAuth2PasswordBearer(tokenUrl="/v1/token/user", auto_error=False)

_public_key = None


def set_public_key(key) -> None:
    global _public_key
    if hasattr(key, "key"):
        _public_key = key.key
    else:
        _public_key = key


def _service_v1_url(path: str) -> Optional[str]:
    base = (DB_SERVICE_BASE_URL or "").rstrip("/")
    if not base:
        return None
    path = path.lstrip("/")
    if base.endswith("/v1"):
        return f"{base}/{path}"
    return f"{base}/v1/{path}"


def _token_verify_url() -> Optional[str]:
    return _service_v1_url("token/verify")


def _candidate_secrets() -> list[str]:
    raw = [
        os.getenv("INTERNAL_PROXY_SECRET"),
        os.getenv("HH_SERVICE_CLIENT_SECRET"),
        os.getenv("DB_CLIENT_SECRET"),
        CLIENT_SECRET,
    ]
    out: list[str] = []
    for value in raw:
        if not value:
            continue
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


def _internal_token_ok(provided: Optional[str]) -> bool:
    if not provided:
        return False
    return provided in set(_candidate_secrets())


async def refresh_public_key() -> bool:
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
        set_public_key(PyJWK(keys[0]))
        logger.info("JWKS public key refreshed from %s", JWKS_URL)
        return True
    except Exception as e:
        logger.error("JWKS refresh failed: %s", e)
        return False


async def _verify_token_via_database(token: str) -> Optional[dict]:
    url = _token_verify_url()
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json={"token": token})
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

    verified = await _verify_token_via_database(token)
    if verified:
        return verified

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
    x_internal_token: Annotated[Optional[str], Header(alias="X-Internal-Token")] = None,
    token: Annotated[Optional[str], Depends(oauth2_sheme)] = None,
):
    """Accept cluster shared-secret (HR→AI) or a Bearer JWT."""
    if _internal_token_ok(x_internal_token):
        return {"sub": "internal-proxy", "type": "service"}
    if x_internal_token and _candidate_secrets():
        logger.warning("X-Internal-Token present but does not match AI configured secrets")
    if token:
        return await validate_bearer_token(token)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
