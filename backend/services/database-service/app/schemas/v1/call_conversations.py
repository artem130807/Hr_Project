from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.db.v1.enums import CallConversationStatus
from app.t2.mapping import transcript_from_payload, words_to_turns


CALL_STATUS_LABELS = {
    CallConversationStatus.pending.value: "Определяется",
    CallConversationStatus.interested.value: "Интерес",
    CallConversationStatus.interview.value: "Собеседование",
    CallConversationStatus.callback.value: "Перезвон",
    CallConversationStatus.rejected.value: "Отказ",
    CallConversationStatus.dropped.value: "Сброс",
}


class CallConversationRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        ser_json_by_alias=True,
    )

    id: int
    filename: str
    description: Optional[str] = None
    payload: Any = None
    call_start_time: Optional[datetime] = Field(None, serialization_alias="callStartTime")
    call_end_time: Optional[datetime] = Field(None, serialization_alias="callEndTime")
    caller_number: Optional[str] = Field(None, serialization_alias="callerNumber")
    operator_number: Optional[str] = Field(None, serialization_alias="operatorNumber")
    duration: Optional[int] = None
    status: str
    status_label: str = Field("", serialization_alias="statusLabel")
    ats_status: Optional[str] = Field(None, serialization_alias="atsStatus")
    direction: Optional[str] = None
    caller_name: Optional[str] = Field(None, serialization_alias="callerName")
    operator_name: Optional[str] = Field(None, serialization_alias="operatorName")
    turns: list[dict] = Field(default_factory=list)

    @classmethod
    def from_row(cls, row) -> "CallConversationRead":
        status = getattr(row, "status", None) or CallConversationStatus.pending.value
        payload = getattr(row, "payload", None)
        words = transcript_from_payload(payload)
        return cls(
            id=row.id,
            filename=row.filename,
            description=row.description,
            payload=payload,
            call_start_time=row.call_start_time,
            call_end_time=row.call_end_time,
            caller_number=row.caller_number,
            operator_number=row.operator_number,
            duration=row.duration,
            status=status,
            status_label=CALL_STATUS_LABELS.get(status, status),
            ats_status=row.ats_status,
            direction=row.direction,
            caller_name=row.caller_name,
            operator_name=row.operator_name,
            turns=words_to_turns(words),
        )
