from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from app.app_logging import logger
from app.clients.api_client import APICLient
import app.config as conf


def _hh_error_reason(status_code: int, detail: object) -> str:
    text = str(detail or "").lower()
    if status_code in (401, 403) and (
        "could not validate" in text
        or "invalid internal proxy token" in text
        or "token has expired" in text
    ):
        return "hh_service_auth_failed"
    if status_code == 503:
        return "hh_service_not_configured"
    if status_code in (400, 403, 404, 409):
        return "hh_api_rejected"
    return "hh_service_http_error"


async def sync_candidate_hh_action(
    hh: Optional[APICLient],
    candidate_id: int,
    action_id: str,
    *,
    message: Optional[str] = None,
) -> Optional[dict]:
    """Best-effort: mirror platform decision onto hh.ru (consider / offer / message).

    Uses the same internal HH proxy as vacancy filter rejects (X-Internal-Token),
    not the JWT APICLient — JWKS drift otherwise looks like ``hh_service_no_response``.
    """
    del hh  # kept in signature for existing call sites / tests
    if not candidate_id or not action_id:
        return {"status": "unavailable", "reason": "hh_service_not_configured"}
    if not (conf.HH_SERVICE_URL or "").strip():
        return {"status": "unavailable", "reason": "hh_service_not_configured"}

    payload = {}
    if message:
        payload["message"] = message

    from app.endpoints.v1.vacancies import _proxy_hh_import

    try:
        result = await _proxy_hh_import(
            "POST",
            f"hh/candidates/{int(candidate_id)}/actions/{action_id}",
            json_body=payload,
            timeout=90.0,
        )
    except HTTPException as exc:
        logger.warning(
            "HH sync %s for candidate %s failed: HTTP %s %s",
            action_id,
            candidate_id,
            exc.status_code,
            exc.detail,
        )
        return {
            "status": "unavailable",
            "reason": _hh_error_reason(exc.status_code, exc.detail),
            "http_status": exc.status_code,
            "detail": exc.detail,
        }
    except Exception as exc:
        logger.warning(
            "HH sync %s for candidate %s failed: %s",
            action_id,
            candidate_id,
            exc,
        )
        return {"status": "unavailable", "reason": "hh_service_request_failed", "detail": str(exc)}

    if not result:
        return {"status": "ok"}
    if isinstance(result, dict) and result.get("status") == "skipped":
        logger.info(
            "HH sync %s for candidate %s skipped: %s",
            action_id,
            candidate_id,
            result.get("reason"),
        )
        return result
    return result if isinstance(result, dict) else {"status": "ok"}
