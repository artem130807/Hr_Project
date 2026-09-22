from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.utils.utils import (
    authenticate_service,
    create_token,
    get_current_user,
    _public_key,
)
from app.config import (
    SERVICE_TOKEN_EXPIRES,
    ALGORITHM,
    ERP_AUTH_ENABLED,
    ERP_JWT_SECRET,
    ERP_JWT_ALGORITHM,
)
from app.db.middleware import get_db
from app.schemas.v1.authorization import (
    ServiceCredentials,
    AuthResponse,
    DecodedToken,
    TokenVerifyCreate,
    RefreshTokenRequest,
    LogoutRequest,
    MeResponse,
)
from app.erp.auth_client import erp_login, erp_refresh, erp_logout, erp_me
from app.erp.auth_bridge import (
    decode_erp_access_token,
    normalize_erp_access_payload,
    erp_pair_to_auth_response,
    me_from_erp,
)
from app.app_logging import logger


router = APIRouter()

_optional_bearer = OAuth2PasswordBearer(tokenUrl="/v1/token/user", auto_error=False)


def _client_meta(request: Request) -> tuple[Optional[str], Optional[str]]:
    ua = request.headers.get("user-agent")
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None
    return ua, ip


def _require_erp_auth():
    if not ERP_AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ERP auth is required (set ERP_AUTH_ENABLED=true and ERP_BASE)",
        )
    if not ERP_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ERP_JWT_SECRET / SECRET_AUTH_JWT / SECRET_JWT is not set",
        )


@router.post('/token/user', status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
async def get_access_token_for_user_endpoint(
    request: Request,
    data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> dict:
    """Panel login — credentials and tokens are owned by erp-backend."""
    _require_erp_auth()
    ua, ip = _client_meta(request)
    pair = await erp_login(data.username, data.password, user_agent=ua, ip=ip)
    logger.info(f"ERP-proxied login for {data.username}")
    return erp_pair_to_auth_response(pair)


@router.post('/token/refresh', status_code=status.HTTP_200_OK, response_model=AuthResponse)
async def refresh_access_token_endpoint(
    body: RefreshTokenRequest,
) -> dict:
    _require_erp_auth()
    pair = await erp_refresh(body.refresh_token)
    logger.info("ERP-proxied token refresh")
    return erp_pair_to_auth_response(pair)


@router.post('/token/logout', status_code=status.HTTP_204_NO_CONTENT)
async def logout_endpoint(
    body: Annotated[Optional[LogoutRequest], Body()] = None,
    access_token: Annotated[Optional[str], Depends(_optional_bearer)] = None,
):
    refresh = body.refresh_token if body else None
    if refresh:
        _require_erp_auth()
        await erp_logout(refresh)
        return None
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provide refresh_token or Authorization Bearer access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # ERP logout requires refresh_token; access-only → client clears session
    logger.info("Logout without refresh_token — no ERP revoke")
    return None


@router.get('/me', response_model=MeResponse, status_code=status.HTTP_200_OK)
async def me_endpoint(
    payload: Annotated[dict, Depends(get_current_user)],
    access_token: Annotated[Optional[str], Depends(_optional_bearer)] = None,
):
    """Current user from ERP JWT (+ optional live /users/me). No local user table."""
    if payload.get("type") == "service":
        raise HTTPException(status_code=403, detail="Service tokens cannot call /me")

    erp_profile = None
    if access_token and ERP_AUTH_ENABLED:
        try:
            erp_profile = await erp_me(access_token)
        except Exception as exc:
            logger.warning(f"/me ERP enrichment failed, using JWT claims: {exc}")

    # If payload already normalized from get_current_user, still decode raw for role dict
    raw = payload
    if access_token and ERP_JWT_SECRET:
        try:
            raw = decode_erp_access_token(access_token)
        except jwt.InvalidTokenError:
            pass

    return me_from_erp(access_payload=raw, erp_me=erp_profile)


@router.post('/token/service', status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
async def get_access_token_for_service_endpoint(
    data: ServiceCredentials,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = await authenticate_service(data.client_id, data.client_secret, db)
    if not service:
        logger.error(f"Service {data.client_id} not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, expires = create_token(
        data={"sub": data.client_id, "type": "service"},
        expires_delta=SERVICE_TOKEN_EXPIRES,
    )
    logger.info(f"Successfully created token for service {data.client_id}")
    return {"access_token": token, "expires": expires.isoformat(), "token_type": "bearer"}


@router.post('/token/verify', status_code=status.HTTP_200_OK, response_model=DecodedToken)
async def verify_token_endpoint(data: TokenVerifyCreate):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if ERP_AUTH_ENABLED and ERP_JWT_SECRET:
        try:
            payload = jwt.decode(data.token, ERP_JWT_SECRET, algorithms=[ERP_JWT_ALGORITHM])
            if payload.get("sub") is None:
                raise credentials_exception
            return normalize_erp_access_payload(payload)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            pass

    try:
        payload = jwt.decode(data.token, _public_key, algorithms=[ALGORITHM])
        if payload.get("sub") is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credentials_exception

    return payload
