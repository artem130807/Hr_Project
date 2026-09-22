import re
import json
from fastapi import APIRouter, HTTPException, Depends, Query
import httpx

from app.schemas.v1.vacancies import VacancyCreate
from app.clients.hh.hh_dictionaries import HHDictionaries
from app.clients.hh.simple_hh_client import SimpleHHClient
from app.dependencies import get_hh_client, get_db_client 
from app.clients.db_client import APICLient
from app.app_logging import logger

router = APIRouter()
# Same handlers, mounted under /v1/internal without JWT (shared-secret only)
internal_router = APIRouter()

_area_dicts = HHDictionaries()


def _extract_duplicate_hh_id(detail: object) -> str | None:
    """Parse existing vacancy id from HH 'duplicate' error payload."""
    text = detail if isinstance(detail, str) else str(detail)
    # Prefer structured JSON after "HH API Error "
    raw = text
    if "HH API Error" in text:
        raw = text.split("HH API Error", 1)[-1].strip()
    try:
        data = json.loads(raw)
    except Exception:
        data = None
    if isinstance(data, dict):
        errors = data.get("errors") or []
        for err in errors:
            if not isinstance(err, dict):
                continue
            if str(err.get("value") or "").lower() != "duplicate":
                continue
            items = err.get("items") or []
            if items and isinstance(items[0], dict) and items[0].get("id") is not None:
                return str(items[0]["id"])
    m = re.search(r'"id"\s*:\s*(\d+)', text)
    return m.group(1) if m else None


_ALLOWED_VACANCY_TYPES = frozenset({"open", "closed", "anonymous", "direct"})
_ALLOWED_BILLING_TYPES = frozenset({"free", "standard", "standard_plus", "premium"})


def _ensure_vacancy_properties(payload: dict) -> dict:
    props = (payload or {}).get("vacancy_properties") or {}
    if not props.get("properties"):
        payload = {**(payload or {})}
        payload["vacancy_properties"] = {
            "properties": [{"property_type": "HH_STANDARD"}]
        }
    return payload


def _ref_id(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        raw = value.get("id")
        return str(raw) if raw is not None and str(raw) != "" else None
    text = str(value).strip()
    return text or None


def _sanitize_hh_payload(payload: dict, *, for_update: bool = False) -> dict:
    """Normalize HH vacancy JSON for create/update.

    Modern HH publish uses vacancy_properties; sending legacy `type` /
    `billing_type` often yields bad_json_data on `type` (especially on edit
    and after duplicate→update). Always omit them.
    """
    out = {**(payload or {})}
    out = _ensure_vacancy_properties(out)

    salary = out.get("salary")
    if isinstance(salary, dict) and "from_" in salary and "from" not in salary:
        salary = {**salary, "from": salary.get("from_")}
        salary.pop("from_", None)
        out["salary"] = salary

    # Never send type/billing_type — HH rejects invalid/legacy combinations
    out.pop("type", None)
    out.pop("billing_type", None)

    if for_update:
        # Extra safety: publication props are also immutable on many edit paths
        out.pop("vacancy_properties", None)

    return _ensure_leaf_area(out)


def _find_area_node(areas: list, area_id: str):
    target = str(area_id)
    for area in areas or []:
        if str(area.get("id")) == target:
            return area
        found = _find_area_node(area.get("areas") or [], target)
        if found:
            return found
    return None


def _ensure_leaf_area(payload: dict) -> dict:
    """HH API requires area.id to be a leaf (city), not a region/country."""
    area = (payload or {}).get("area") or {}
    area_id = area.get("id") if isinstance(area, dict) else None
    if not area_id:
        raise HTTPException(
            status_code=400,
            detail="Укажите город (местоположение) перед публикацией на HH.ru",
        )
    try:
        tree = _area_dicts.get_areas() or []
    except Exception as e:
        logger.warning(f"Could not load HH areas dictionary: {e}")
        return payload

    node = _find_area_node(tree, str(area_id))
    if not node:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Местоположение area_id={area_id} не найдено в справочнике HH. "
                "Выберите город в карточке вакансии, сохраните и опубликуйте снова."
            ),
        )
    children = node.get("areas") or []
    if children:
        name = node.get("name") or area_id
        raise HTTPException(
            status_code=400,
            detail=(
                f"HH.ru принимает только город, а не регион. Сейчас выбрано «{name}» "
                f"(id={area_id}). Откройте вакансию, выберите город в списке, сохраните "
                "и нажмите «На HH.ru» снова."
            ),
        )
    return payload


@router.post("/vacancy/{vacancy_id}/draft")
async def create_vacancy_draft_endpoint(
    vacancy_id: int,
    hh: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client)
):
    """
    Создание черновика вакансии на HH по vacancy_id
    """
    try:
        vacancy = await db.get(f'/vacancy/{vacancy_id}/map-to-hh', raise_on_error=True)
        if not vacancy:
            raise HTTPException(404, f'Вакансия #{vacancy_id}: map-to-hh вернул пустой ответ')
        response = await hh.post_vacancy_draft(vacancy)
        return response
    except HTTPException as e:
        logger.error(f"Error creating vacancy draft: {str(e)}")
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании черновика вакансии: {e}")


@router.post("/vacancy/{vacancy_id}")
async def publish_vacancy_endpoint(
    vacancy_id: int,
    client: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client)
):
    """
    Публикация вакансии на HH.ru.

    Портреты/слоты НЕ блокируют публикацию — они нужны боту, но не API HH.
    """
    try:
        vacancy = await db.get(f'/vacancy/{vacancy_id}', raise_on_error=True)
        if not vacancy:
            raise HTTPException(404, f'Вакансия #{vacancy_id} не найдена в database-service')

        hh_vacancy = await db.get(f'/vacancy/{vacancy_id}/map-to-hh', raise_on_error=True)
        if not hh_vacancy:
            raise HTTPException(404, f'Не удалось подготовить данные вакансии #{vacancy_id} для HH (map-to-hh)')

        # If already linked OR we know HH id — update only (never POST with type fields)
        existing_hh_id = vacancy.get("hh_vacancy_id")
        if existing_hh_id:
            hh_vacancy = _sanitize_hh_payload(hh_vacancy, for_update=True)
            response = await client.update_vacancy(str(existing_hh_id), hh_vacancy)
            hh_vacancy_id = str(existing_hh_id)
        else:
            create_payload = _sanitize_hh_payload(hh_vacancy, for_update=False)
            try:
                response = await client.post_vacancy(create_payload)
            except HTTPException as e:
                dup_id = _extract_duplicate_hh_id(e.detail)
                if not dup_id:
                    raise
                logger.warning(
                    "HH duplicate on publish for vacancy %s — linking to existing hh id %s",
                    vacancy_id,
                    dup_id,
                )
                # Persist link immediately so later delete/update can find HH id
                # even if the follow-up update payload is rejected.
                try:
                    await db.patch(
                        f"/vacancy/{vacancy_id}",
                        json={
                            "hh_vacancy_id": str(dup_id),
                            "hh_vacancy_url": f"https://hh.ru/vacancy/{dup_id}",
                        },
                        raise_on_error=True,
                    )
                except Exception as link_err:
                    logger.warning(
                        "Failed to persist HH link for vacancy %s → %s: %s",
                        vacancy_id,
                        dup_id,
                        link_err,
                    )
                response = await client.update_vacancy(
                    dup_id,
                    _sanitize_hh_payload(hh_vacancy, for_update=True),
                )
                hh_vacancy_id = dup_id
            else:
                if not response or not isinstance(response, dict):
                    raise HTTPException(502, "HH вернул пустой ответ при публикации вакансии")
                hh_vacancy_id = response.get("id")
                if not hh_vacancy_id:
                    raise HTTPException(500, "HH не вернул ID вакансии")
                hh_vacancy_id = str(hh_vacancy_id)

        # 2. Получение полной информации о вакансии
        vacancy_full = await client.get_vacancy(hh_vacancy_id) or {}
        hh_url = vacancy_full.get("alternate_url") or f"https://hh.ru/vacancy/{hh_vacancy_id}"

        db_response = await db.patch(
            f'/vacancy/{vacancy_id}',
            json={
                "hh_vacancy_id": str(hh_vacancy_id),
                "hh_vacancy_url": hh_url
            },
            raise_on_error=True,
        )

        # Автоматическая активация автопоиска для размещенной вакансии
        try:
            search = await db.get(f'/autosearch/vacancy/{vacancy_id}')
            if search is None:
                autosearch_payload = {
                    "vacancy_id": vacancy_id,
                    "daily_limit": 0,
                    "sent_today": 0,
                    "total_sent": 0,
                    "active": True,
                    "invite_limit": 10
                }
                search = await db.post("/autosearch", json=autosearch_payload)
                logger.info(f"Created autosearch for vacancy {vacancy_id}, autosearch_id: {(search or {}).get('id')}")
            else:
                await db.post(f"/autosearch/{search['id']}/activate")
                logger.info(f"Activated autosearch for vacancy {vacancy_id}, autosearch_id: {search['id']}")
        except Exception as e:
            logger.error(f"Error activating autosearch for vacancy {vacancy_id}: {str(e)}")

        return {
            "status": "ok",
            "hh_vacancy_id": hh_vacancy_id,
            "alternate_url": hh_url,
            "db_vacancy_updated": True if db_response else False,
            "raw": response,
        }
    except HTTPException as e:
        logger.error(f"Error posting vacancy: {str(e)}")
        raise e

    except Exception as e:
        logger.error(f"Error posting vacancy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при публикации вакансии: {e}")


@router.put("/vacancy/{vacancy_id}")
async def update_published_vacancy_endpoint(
    vacancy_id: int,
    client: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client),
):
    """Sync local vacancy changes to an already published HH vacancy."""
    vacancy = await db.get(f"/vacancy/{vacancy_id}", raise_on_error=True)
    if not vacancy:
        raise HTTPException(404, f"Вакансия #{vacancy_id} не найдена")

    hh_id = vacancy.get("hh_vacancy_id")
    if not hh_id:
        raise HTTPException(
            409,
            "Вакансия ещё не опубликована на HH.ru — сначала опубликуйте её",
        )

    hh_payload = await db.get(f"/vacancy/{vacancy_id}/map-to-hh", raise_on_error=True)
    if not hh_payload:
        raise HTTPException(404, "Не удалось подготовить данные вакансии для HH")

    hh_payload = _sanitize_hh_payload(hh_payload, for_update=True)
    response = await client.update_vacancy(str(hh_id), hh_payload)

    vacancy_full = await client.get_vacancy(str(hh_id)) or {}
    hh_url = vacancy_full.get("alternate_url") or vacancy.get("hh_vacancy_url")
    if hh_url and hh_url != vacancy.get("hh_vacancy_url"):
        await db.patch(
            f"/vacancy/{vacancy_id}",
            json={"hh_vacancy_url": hh_url},
            raise_on_error=True,
        )

    return {
        "status": "ok",
        "hh_vacancy_id": str(hh_id),
        "alternate_url": hh_url,
        "raw": response,
    }


@router.delete("/vacancy/{vacancy_id}")
async def remove_published_vacancy_endpoint(
    vacancy_id: int,
    client: SimpleHHClient = Depends(get_hh_client),
    db: APICLient = Depends(get_db_client),
):
    """Archive+hide vacancy on HH and clear local HH links (does not delete local row)."""
    vacancy = await db.get(f"/vacancy/{vacancy_id}", raise_on_error=True)
    if not vacancy:
        raise HTTPException(404, f"Вакансия #{vacancy_id} не найдена")

    hh_id = vacancy.get("hh_vacancy_id")
    if not hh_id:
        url = str(vacancy.get("hh_vacancy_url") or "")
        m = re.search(r"/vacancy/(\d+)", url)
        if m:
            hh_id = m.group(1)

    hh_removed = False
    if hh_id:
        await client.delete_vacancy(str(hh_id))
        hh_removed = True
        await db.patch(
            f"/vacancy/{vacancy_id}",
            json={"hh_vacancy_id": None, "hh_vacancy_url": None},
            raise_on_error=True,
        )
        try:
            search = await db.get(f"/autosearch/vacancy/{vacancy_id}")
            if search and search.get("id"):
                await db.post(f"/autosearch/{search['id']}/deactivate")
        except Exception as e:
            logger.warning(f"Autosearch deactivate failed for vacancy {vacancy_id}: {e}")

    return {
        "status": "ok",
        "hh_removed": hh_removed,
        "hh_vacancy_id": str(hh_id) if hh_id else None,
    }


@router.delete("/hh-vacancy/{hh_vacancy_id}")
async def remove_hh_vacancy_by_hh_id_endpoint(
    hh_vacancy_id: str,
    client: SimpleHHClient = Depends(get_hh_client),
):
    """Archive+hide by HH vacancy id only (used after local row is already deleted)."""
    await client.delete_vacancy(str(hh_vacancy_id))
    return {"status": "ok", "hh_removed": True, "hh_vacancy_id": str(hh_vacancy_id)}


# Internal aliases (auth via X-Internal-Token on the router, not JWT/JWKS)
internal_router.add_api_route(
    "/vacancy/{vacancy_id}",
    publish_vacancy_endpoint,
    methods=["POST"],
)
internal_router.add_api_route(
    "/vacancy/{vacancy_id}",
    update_published_vacancy_endpoint,
    methods=["PUT"],
)
internal_router.add_api_route(
    "/vacancy/{vacancy_id}",
    remove_published_vacancy_endpoint,
    methods=["DELETE"],
)
internal_router.add_api_route(
    "/hh-vacancy/{hh_vacancy_id}",
    remove_hh_vacancy_by_hh_id_endpoint,
    methods=["DELETE"],
)
