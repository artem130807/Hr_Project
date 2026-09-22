import os

from fastapi import Header, HTTPException, status


def _candidate_secrets() -> list[str]:
    raw = [
        os.getenv("INTERNAL_PROXY_SECRET"),
        os.getenv("HH_SERVICE_CLIENT_SECRET"),
        os.getenv("DB_CLIENT_SECRET"),
    ]
    out: list[str] = []
    for value in raw:
        if not value:
            continue
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


async def verify_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
):
    """Shared-secret auth for database-service → hh-service proxy calls."""
    expected = _candidate_secrets()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_PROXY_SECRET / HH_SERVICE_CLIENT_SECRET is not configured",
        )
    if not x_internal_token or x_internal_token not in expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal proxy token",
        )
    return True
