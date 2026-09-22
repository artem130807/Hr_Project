"""HH dictionaries for the SPA.

Tries hh-service first (via internal proxy / service JWT — same path as
employer-vacancies), then falls back to public api.hh.ru so vacancy
creation keeps working even if hh-service is down.
"""
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

HH_USER_AGENT = {"User-Agent": "HR-Platform/1.0 (dictionary-proxy)"}
DICT_FROM_HH_DICTIONARIES = {
    "vacancy_type": "vacancy_type",
    "work_format": "work_format",
    "experience": "experience",
    "employment": "employment",
    "schedule": "schedule",
}


async def _fetch_public(path: str) -> Any:
    async with httpx.AsyncClient(timeout=20.0, headers=HH_USER_AGENT) as client:
        if path in ("areas", "professional_roles"):
            resp = await client.get(f"https://api.hh.ru/{path}")
            resp.raise_for_status()
            return resp.json()

        key = DICT_FROM_HH_DICTIONARIES.get(path)
        if not key:
            raise HTTPException(status_code=404, detail=f"Unknown dictionary '{path}'")
        resp = await client.get("https://api.hh.ru/dictionaries")
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get(key)
        if items is None:
            raise HTTPException(status_code=502, detail=f"HH dictionary '{path}' missing upstream")
        return items


async def _proxy(path: str):
    # Prefer the same DB→HH auth as publish/import (X-Internal-Token), not the
    # shared APICLient Bearer which fails when PRIVATE_KEY drifts across pods.
    try:
        from app.endpoints.v1.vacancies import _proxy_hh_import

        data = await _proxy_hh_import("GET", path, timeout=20.0)
        if data is not None:
            return data
    except HTTPException:
        pass
    except Exception:
        pass
    try:
        return await _fetch_public(path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HH dictionary '{path}' unavailable: {exc}") from exc


@router.get("/areas")
async def get_areas():
    return await _proxy("areas")


@router.get("/professional_roles")
async def get_professional_roles():
    return await _proxy("professional_roles")


@router.get("/vacancy_type")
async def get_vacancy_type():
    return await _proxy("vacancy_type")


@router.get("/work_format")
async def get_work_format():
    return await _proxy("work_format")


@router.get("/experience")
async def get_experience():
    return await _proxy("experience")


@router.get("/employment")
async def get_employment():
    return await _proxy("employment")


@router.get("/schedule")
async def get_schedule():
    return await _proxy("schedule")
