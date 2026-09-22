from fastapi import APIRouter, Depends, HTTPException

from app.schemas.v1.autosearch import AutoSearchCreate, AutoSearchRead
from app.dependencies import get_db_client, get_hh_client
from app.clients.db_client import APICLient
from app.app_logging import logger


router = APIRouter()


@router.get('/autosearch/active', response_model=list[AutoSearchRead])
async def list_active_autosearches_endpoint(
    db: APICLient = Depends(get_db_client)
):
    """
    Returns list of active autosearches
    """
    items = await db.get('/autosearch/active')
    if items is None:
        raise HTTPException(500, "database-service not available")
    
    return items


@router.get('/autosearch/vacancies/available')
async def list_vacancies_available_for_autosearch(
    db: APICLient = Depends(get_db_client)
):
    """
    Returns vacancies available to activate autosearch 
    """
    published_vacancies = await db.get('/vacancies/published')
    if published_vacancies is None:
        raise HTTPException(500, "database-service not available")
    
    activated_searches = await db.get('/autosearch/active')
    if activated_searches is None:
        raise HTTPException(500, "database-service not available")
    
    active_ids = [search['vacancy_id'] for search in activated_searches]
    available_vacancies = [vacancy for vacancy in published_vacancies if vacancy['id'] not in active_ids]
    
    return available_vacancies


@router.post('/autosearch/{vacancy_id}/activate')
async def autosearch_activate_endpoint(
    vacancy_id: int,
    db: APICLient = Depends(get_db_client)
):
    """
    Activates autosearch for vacancy even if autosearch doesn't exist yet
    """
    search = await db.get(f'/autosearch/vacancy/{vacancy_id}')
    if search is None:
        vacancy = await db.get(f'/vacancy/{vacancy_id}')
        if not vacancy:
            raise HTTPException(404, 'Vacancy not found')
        if vacancy['hh_vacancy_id'] is None:
            raise HTTPException(409, 'Vacancy not published on hh.ru')
        payload = {
        "vacancy_id": vacancy_id,
        "daily_limit": 0,
        "sent_today": 0,
        "total_sent": 0,
        "active": True,
        "invite_limit": 10
        }
        search = await db.post(f"/autosearch", json=payload)
        if not search:
            raise HTTPException(500, "database-service not available")
        
    response = await db.post(f"/autosearch/{search['id']}/activate")
    if not response:
        raise HTTPException(404, "Autosearch not found")
    
    return {"active": True}


@router.post('/autosearch/{vacancy_id}/deactivate')
async def autosearch_activate_endpoint(
    vacancy_id: int,
    db: APICLient = Depends(get_db_client)
):
    """
    Deactivates autosearch for vacancy
    """
    search = await db.get(f'/autosearch/vacancy/{vacancy_id}')
    if not search:
        raise HTTPException(404, 'Search for this vacancy not found')
    autosearch_id = search['id']
    response = await db.post(f"/autosearch/{autosearch_id}/deactivate")
    if not response:
        raise HTTPException(404, "Autosearch not found")
    
    return {"active": False}


@router.patch('/autosearch/{vacancy_id}/invite-limit')
async def autosearch_set_invite_limit_endpoint(
    vacancy_id: int,
    invite_limit: int,
    db: APICLient = Depends(get_db_client)
):
    """
    Sets invite limit for autosearch
    """
    if invite_limit <= 0:
        raise HTTPException(400, "Invite limit must be positive integer")
    
    autosearch = await db.get(f'/autosearch/vacancy/{vacancy_id}')
    if not autosearch:
        raise HTTPException(404, 'Autosearch not found for this vacancy')
    autosearch_id = autosearch['id']
    
    response = await db.patch(
        f'/autosearch/{autosearch_id}',
        json={"invite_limit": invite_limit}
    )
    if not response:
        raise HTTPException(500, "database-service not available")
    
    return response