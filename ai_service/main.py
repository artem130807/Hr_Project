import os
import asyncio
import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.endpoints.v1.candidates import router as candidate_router
from app.endpoints.v1.vacancies import router as vacancy_router
from app.endpoints.v1.auth import router as auth_router
from app.endpoints.v1.tests import router as test_router
from app.utils.auth import verify_external_or_internal
from app.config import v1
from app.runtime import run_loops

import httpx
from jwt import PyJWKSet

from app.config import JWKS_URL
from app.utils.auth import set_public_key
from app.app_logging import logger

app = FastAPI(
    title="AI Service",
    description="Service for managing AI functions",
    version="1"
)

# CORS: явный allow-list вместо wildcard (wildcard + credentials небезопасен)
_cors_origins_env = os.getenv("CORS_ORIGINS")
try:
    _cors_origins = _cors_origins_env.split(",") if _cors_origins_env else None
except Exception:
    _cors_origins = None
if not _cors_origins:
    _cors_origins = [
        "https://alt-lovat.vercel.app",
        "https://hr-web.alt-cargo.tw1.ru",
        "http://localhost:3000",
    ]

app.add_middleware(CORSMiddleware,
               allow_origins=_cors_origins,
               allow_credentials=True,
               allow_methods=["*"],
               allow_headers=["*"],
               )

app.include_router(auth_router, prefix=v1, tags=["Auth"])
app.include_router(test_router, prefix=v1, tags=["Tests"], dependencies=[Depends(verify_external_or_internal)])
app.include_router(candidate_router, prefix=v1, tags=["Candidates"], dependencies=[Depends(verify_external_or_internal)])
app.include_router(vacancy_router, prefix=v1, tags=["Vacancies"], dependencies=[Depends(verify_external_or_internal)])

_stop_event: asyncio.Event | None = None
_loop_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup_event():
    logger.info("Starting up the AI Service application.")
    # JWKS fetch с таймаутом и ретраями (как в hh-service)
    last_err = None
    for attempt in range(10):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(JWKS_URL, timeout=5.0)
                response.raise_for_status()
            jwks = PyJWKSet.from_dict(response.json())
            set_public_key(jwks.keys[0])
            logger.info("JWKS public key loaded successfully.")
            last_err = None
            break
        except Exception as e:
            last_err = e
            if attempt == 9:
                break
            await asyncio.sleep(3 * (attempt + 1))
    if last_err is not None:
        raise RuntimeError(f"Failed to load JWKS from {JWKS_URL}: {last_err}")

    global _stop_event, _loop_task
    _stop_event = asyncio.Event()
    _loop_task = asyncio.create_task(run_loops(_stop_event))


@app.on_event("shutdown")
async def shutdown_event():
    global _stop_event, _loop_task
    if _stop_event is not None:
        _stop_event.set()
    if _loop_task is not None:
        _loop_task.cancel()
        try:
            await _loop_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )