"""HTTP triggers from hr-worker to hh-service job endpoints."""
from __future__ import annotations

import httpx

from app.app_logging import logger
import app.config as conf


def _hh_base() -> str:
    return (conf.HH_SERVICE_URL or "").rstrip("/")


def _proxy_secrets() -> list[str]:
    secrets = list(getattr(conf, "INTERNAL_HH_PROXY_TOKENS", None) or [])
    token = getattr(conf, "INTERNAL_HH_PROXY_TOKEN", None)
    if token and str(token) not in secrets:
        secrets.append(str(token))
    return secrets


async def trigger_hh_job(job: str, *, timeout: float) -> bool:
    """POST /v1/internal/jobs/{job} with the same X-Internal-Token as vacancy proxy."""
    base = _hh_base()
    if not base:
        logger.warning("HH job %s skipped — HH_SERVICE_INTERNAL is not configured", job)
        return False
    secrets = _proxy_secrets()
    if not secrets:
        logger.warning("HH job %s skipped — no internal proxy token", job)
        return False

    url = f"{base}/v1/internal/jobs/{job}"
    last_status = None
    last_body = ""
    async with httpx.AsyncClient(timeout=timeout) as client:
        for secret in secrets:
            try:
                resp = await client.post(url, headers={"X-Internal-Token": str(secret)})
            except httpx.RequestError as exc:
                logger.warning("HH job %s unreachable: %s", job, exc)
                return False
            if resp.is_success:
                return True
            last_status = resp.status_code
            last_body = (resp.text or "")[:300]
            if resp.status_code not in (401, 403):
                break
    logger.warning("HH job %s failed: HTTP %s %s", job, last_status, last_body)
    return False
