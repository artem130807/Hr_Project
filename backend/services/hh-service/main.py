import json
import os

import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.endpoints.v1.hh_auth import router as hh_auth_router
from app.endpoints.v1.vacancies import router as vacancy_router, internal_router as vacancy_internal_router
from app.endpoints.v1.webhook_subscription import router as webhook_subscription_router
from app.endpoints.v1.negotiation import router as negotiation_webhook_router
from app.endpoints.v1.hh_dictionaries import router as hh_dictionaries_router
from app.endpoints.v1.hh_auth_link import router as hh_auth_link_router
from app.endpoints.v1.autosearch import router as autosearch_router
from app.endpoints.v1.hh_dictionaries_mapping import router as hh_dictionaries_mapping_router
from app.endpoints.v1.auth import router as auth_router
from app.endpoints.v1.mock_test import router as test_router
from app.endpoints.v1.dev_endpoints import router as dev_router
from app.endpoints.v1.internal_jobs import router as internal_jobs_router

from app.dependencies import get_db_client, get_hh_client, get_ai_client

from app.utils.auth import verify_external_access, verify_external_or_internal, refresh_public_key
from app.utils.internal_auth import verify_internal_token
from app.scheduler.scheduler import init_scheduler
from app.config import V1
from app.endpoints.v1.hh_import import router as hh_import_router

app = FastAPI(
    title="HH Service",
    description="Service for handling HeadHunter related operations",
    version="1"
)

_cors_origins_env = os.getenv("CORS_ORIGINS")
try:
    _cors_origins = json.loads(_cors_origins_env) if _cors_origins_env else None
except (ValueError, TypeError):
    _cors_origins = None
if not _cors_origins:
    _cors_origins = [
        "https://alt-lovat.vercel.app",  # продовый фронт
        "https://hr-web.alt-cargo.tw1.ru",
        "http://localhost:3000",         # фронт у разработчика
    ]

app.add_middleware(CORSMiddleware,
               allow_origins=_cors_origins,
               allow_credentials=True,
               allow_methods=["*"],
               allow_headers=["*"],
               )

app.include_router(auth_router, prefix=V1, tags=["Auth"])
app.include_router(hh_auth_router, prefix=V1, tags=["HH Auth"])
app.include_router(hh_auth_link_router, prefix=V1, tags=["HH Auth Link"], dependencies=[Depends(verify_external_or_internal)])
app.include_router(test_router, prefix=V1, tags=["TEST"], dependencies=[Depends(verify_external_access)])
app.include_router(dev_router, prefix=V1, tags=["DEV"], dependencies=[Depends(verify_external_access)])
app.include_router(internal_jobs_router, prefix=V1)
app.include_router(autosearch_router, prefix=V1, tags=["Autosearch"], dependencies=[Depends(verify_external_access)])
# Dual auth: X-Internal-Token (DB proxy) OR Bearer JWT
app.include_router(vacancy_router, prefix=V1, tags=["Vacancy"], dependencies=[Depends(verify_external_or_internal)])
# Explicit internal mount (shared secret only) — kept for compatibility
app.include_router(
    vacancy_internal_router,
    prefix=f"{V1}/internal",
    tags=["Vacancy Internal"],
    dependencies=[Depends(verify_internal_token)],
)
app.include_router(webhook_subscription_router, prefix=V1, tags=["Subscription on hh webhooks"], dependencies=[Depends(verify_external_access)])
app.include_router(negotiation_webhook_router, prefix=V1, tags=["Negotiation Webhooks"])
app.include_router(hh_dictionaries_mapping_router, prefix=V1, tags=["HH Dictionaries Mapping"], dependencies=[Depends(verify_external_access)])
# Dual auth: DB dictionary proxy uses X-Internal-Token (same as hh_import)
app.include_router(
    hh_dictionaries_router,
    prefix=V1,
    tags=["HH Dictionaries"],
    dependencies=[Depends(verify_external_or_internal)],
)
app.include_router(hh_import_router, prefix=V1, tags=["HH Import"], dependencies=[Depends(verify_external_or_internal)])


@app.get(f"{V1}/proxy-auth-info", tags=["Health"])
async def proxy_auth_info():
    """Unauthenticated capability probe for database-service publish proxy."""
    from app.utils.auth import _candidate_secrets

    return {
        "ok": True,
        "proxy_auth": "dual-v2",
        "internal_routes": True,
        "internal_secret_configured": bool(_candidate_secrets()),
        "secret_candidates": len(_candidate_secrets()),
    }


@app.post("/debug/autosearch")
async def run_autosearch_debug(_: dict = Depends(verify_external_access)):
    from app.tasks.autosearch import autosearch
    try:
        result = await autosearch(await get_db_client(), await get_hh_client(), await get_ai_client())
    except Exception as e:
        raise HTTPException(500, str(e))
    if result:
        return {"status": "done"}


@app.post("/debug/auto-reject-filtered")
async def run_auto_reject_filtered_debug(_: dict = Depends(verify_external_access)):
    from app.tasks.auto_reject_filtered import auto_reject_filtered
    try:
        summary = await auto_reject_filtered(await get_db_client(), await get_hh_client())
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"status": "done", "summary": summary}


@app.on_event("startup")
async def startup():
    import asyncio
    for attempt in range(10):
        try:
            ok = await refresh_public_key()
            if not ok:
                raise RuntimeError("JWKS refresh returned False")
            break
        except Exception:
            if attempt == 9:
                raise
            await asyncio.sleep(3 * (attempt + 1))
    # Periodic HH jobs: hr-worker → POST /v1/internal/jobs/* (not APScheduler).
    init_scheduler()


if __name__=="__main__":
    uvicorn.run("main:app",
                host="0.0.0.0",
                port=8003
                )