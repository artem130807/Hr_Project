from typing import Annotated

import jwt
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status

from app.config import ALGORITHM
from app.app_logging import logger

oauth2_sheme = OAuth2PasswordBearer(tokenUrl='/v1/token/user')

_public_key = None


def set_public_key(key) -> None:
    global _public_key
    _public_key = key


async def get_current_user(token: Annotated[str, Depends(oauth2_sheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = jwt.decode(token, _public_key, algorithms=[ALGORITHM])
        if payload.get("sub") is None:
            logger.error("Token verification failed. (no subject in token)")
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        logger.error("Token verification failed. (invalid token)")
        raise credentials_exception

    return payload


async def verify_external_access(user: Annotated[str, Depends(get_current_user)]):
    return user
