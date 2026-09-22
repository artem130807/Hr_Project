from pydantic import BaseModel

from app.db.v1.enums import CandidateStatus


class Status(BaseModel):
    status: CandidateStatus
    label: str
    stage: str
    state: str
    next_action: str
    allowed_transitions: list[CandidateStatus]

class StatusDict(BaseModel):
    items: list[Status]
