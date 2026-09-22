from fastapi import APIRouter, Depends, HTTPException

from app.utils.resume_parsing import parse_hh_resume_to_candidate
from app.schemas.v1.candidates import CandidateCreate
from app import mock
from app.dependencies import get_hh_client
from app.clients.hh.simple_hh_client import SimpleHHClient
from app.utils.negotiation import get_negotiation_id_in_response_collection


router = APIRouter()


@router.post('/test', response_model=CandidateCreate)
async def resume_mapper_preview():
    return parse_hh_resume_to_candidate(mock.resume_example)


@router.post('/test/nid-search')
async def nid_search_test_endpoint(
    chat_id: str,
    vacancy_id: str,
    hh: SimpleHHClient = Depends(get_hh_client)
):
    return await get_negotiation_id_in_response_collection(hh, vacancy_id, chat_id)
