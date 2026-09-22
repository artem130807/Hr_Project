from datetime import datetime, timedelta

from app.db.v1.enums import CallConversationStatus
from app.t2.mapping import (
    extract_transcript_words,
    normalize_call_record,
    transcript_from_payload,
    words_to_turns,
)


USER_SHAPE = {
    "id": 123456789,
    "filename": "recording_2025-08-25_14-30-15.mp3",
    "callStartTime": "2025-08-25T14:30:15+03:00",
    "callEndTime": "2025-08-25T14:35:42+03:00",
    "callerNumber": "+79001234567",
    "operatorNumber": "+79007654321",
    "duration": 327,
    "status": "ANSWERED",
}

OFFICIAL_SHAPE = {
    "uuid": "89f69952-fad7-4142-8d5d-1b1e11138813",
    "date": "2022-07-15T07:27:06.348Z",
    "callType": "OUTGOING",
    "destinationNumber": "79104739472",
    "callerNumber": "79000258890",
    "callerName": "Анастасия Исаева",
    "calleeNumber": "79104739472",
    "calleeName": "Оля Заплаткина",
    "callDuration": 20,
    "conversationDuration": 6,
    "callStatus": "ANSWERED_BY_ORIGINAL_CLIENT",
    "recordFileName": "2022-08-12/mo_166030684915821522",
}

STT = [
    {"channel": "B", "startTime": 0.3, "endTime": 1.08, "word": "информируем"},
    {"channel": "B", "startTime": 1.08, "endTime": 1.26, "word": "что"},
    {"channel": "B", "startTime": 1.68, "endTime": 2.55, "word": "разговор"},
    {"channel": "B", "startTime": 2.55, "endTime": 3.78, "word": "записывается"},
    {"channel": "A", "startTime": 5.0, "endTime": 5.4, "word": "хорошо"},
]


def test_hr_call_statuses():
    assert CallConversationStatus.pending.value == "pending"
    assert CallConversationStatus.interested.value == "interested"
    assert CallConversationStatus.interview.value == "interview"
    assert CallConversationStatus.callback.value == "callback"
    assert CallConversationStatus.rejected.value == "rejected"
    assert CallConversationStatus.dropped.value == "dropped"


def test_normalize_user_shape():
    mapped = normalize_call_record(USER_SHAPE)
    assert mapped["filename"] == "recording_2025-08-25_14-30-15.mp3"
    assert mapped["ats_id"] == "123456789"
    assert mapped["caller_number"] == "+79001234567"
    assert mapped["operator_number"] == "+79007654321"
    assert mapped["duration"] == 327
    assert mapped["ats_status"] == "ANSWERED"
    assert mapped["call_start_time"] == datetime.fromisoformat("2025-08-25T14:30:15+03:00")
    assert mapped["call_end_time"] == datetime.fromisoformat("2025-08-25T14:35:42+03:00")


def test_normalize_official_shape_computes_end():
    mapped = normalize_call_record(OFFICIAL_SHAPE)
    assert mapped["filename"] == "2022-08-12/mo_166030684915821522"
    assert mapped["ats_id"] == "89f69952-fad7-4142-8d5d-1b1e11138813"
    assert mapped["duration"] == 6
    assert mapped["direction"] == "outgoing"
    assert mapped["operator_number"] == "79104739472"
    start = mapped["call_start_time"]
    assert start.tzinfo is not None
    assert mapped["call_end_time"] == start + timedelta(seconds=6)


def test_skips_unrecorded_without_filename():
    assert normalize_call_record({"id": 1, "callStatus": "NOT_ANSWERED_COMMON"}) is None


def test_words_to_turns_groups_channel_b_as_hr():
    turns = words_to_turns(STT)
    assert len(turns) == 2
    assert turns[0]["speaker"] == "hr"
    assert turns[0]["text"] == "информируем что разговор записывается"
    assert turns[0]["at"] == "00:00"
    assert turns[1]["speaker"] == "candidate"
    assert turns[1]["text"] == "хорошо"


def test_transcript_from_payload_shapes():
    assert extract_transcript_words(STT)[0]["word"] == "информируем"
    assert transcript_from_payload({"transcript": STT})[0]["word"] == "информируем"
    assert transcript_from_payload(STT)[-1]["word"] == "хорошо"


def test_normalize_rejects_non_dict():
    assert normalize_call_record(None) is None
    assert normalize_call_record("x") is None


def test_infer_direction_from_operator_as_caller():
    mapped = normalize_call_record(
        {
            "filename": "x.mp3",
            "callerNumber": "+7900",
            "operatorNumber": "+7900",
        }
    )
    assert mapped["direction"] == "outgoing"


def test_extract_transcript_skips_empty_words():
    words = extract_transcript_words(
        {
            "items": [
                {"channel": "A", "startTime": 0, "endTime": 1, "word": "  "},
                {"channel": "A", "startTime": 1, "endTime": 2, "word": "да"},
                "skip-me",
            ]
        }
    )
    assert words == [{"channel": "A", "startTime": 1.0, "endTime": 2.0, "word": "да"}]
