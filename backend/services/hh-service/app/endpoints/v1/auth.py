from typing import Annotated

import httpx

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas.v1.auth import AuthResponse
from app.app_logging import logger
from app.config import DB_SERVICE_URL


router = APIRouter()


@router.post('/token/user', status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
async def get_access_token_for_user_endpoint(data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{DB_SERVICE_URL}/token/user",
            data={
                "username": data.username, 
                "password": data.password
                },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
    if response.status_code != 201:
        logger.error(f"Error getting user token: {response.text}")
        raise HTTPException(401, "Invalid username or password")
    return response.json()