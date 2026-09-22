from fastapi import APIRouter

from app.db.v1.enums import CandidateStatus
from app.schemas.v1.dictionaries import StatusDict
from app.candidates.statuses import status_catalog_item


router = APIRouter()


@router.get('/dict/status', response_model=StatusDict)
async def get_status_dict_endpoint():
    return {"items":
        [
            status_catalog_item(status)
            for status in CandidateStatus
        ]
    }
