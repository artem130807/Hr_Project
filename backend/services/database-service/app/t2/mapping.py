"""Normalize T2 ATS call-record payloads (official OpenAPI + compact CRM shape)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

_OUTGOING_CALL_TYPES = frozenset(
    {"OUTGOING", "CRM_OUTGOING", "CRM_CALLBACK", "CALLBACK"}
)


def _first(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _as_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def infer_direction(record: dict, *, operator_number: Optional[str]) -> str:
    call_type = _as_str(_first(record.get("callType"), record.get("call_type")))
    if call_type and call_type.upper() in _OUTGOING_CALL_TYPES:
        return "outgoing"
    direction = _as_str(_first(record.get("direction"), record.get("callDirection")))
    if direction:
        lowered = direction.lower()
        if lowered in {"outgoing", "outbound", "исходящий"}:
            return "outgoing"
        if lowered in {"incoming", "inbound", "входящий"}:
            return "incoming"
    caller = _as_str(_first(record.get("callerNumber"), record.get("caller_number")))
    if operator_number and caller and operator_number == caller:
        return "outgoing"
    return "incoming"


def normalize_call_record(raw: Any) -> Optional[dict]:
    """Map an ATS record to a stable internal dict. Returns None if no filename."""
    if not isinstance(raw, dict):
        return None
    filename = _as_str(
        _first(raw.get("filename"), raw.get("recordFileName"), raw.get("record_file_name"))
    )
    if not filename:
        return None

    ats_id = _as_str(_first(raw.get("id"), raw.get("uuid"), raw.get("atsId")))
    start = parse_datetime(
        _first(raw.get("callStartTime"), raw.get("call_start_time"), raw.get("date"), raw.get("startDate"))
    )
    duration = _as_int(
        _first(
            raw.get("duration"),
            raw.get("conversationDuration"),
            raw.get("callDuration"),
        )
    )
    end = parse_datetime(_first(raw.get("callEndTime"), raw.get("call_end_time")))
    if end is None and start is not None and duration is not None:
        end = start + timedelta(seconds=max(0, duration))

    caller_number = _as_str(_first(raw.get("callerNumber"), raw.get("caller_number")))
    operator_number = _as_str(
        _first(
            raw.get("operatorNumber"),
            raw.get("operator_number"),
            raw.get("calleeNumber"),
            raw.get("callee_number"),
            raw.get("destinationNumber"),
        )
    )
    ats_status = _as_str(_first(raw.get("status"), raw.get("callStatus"), raw.get("call_status")))
    caller_name = _as_str(_first(raw.get("callerName"), raw.get("caller_name")))
    operator_name = _as_str(
        _first(raw.get("operatorName"), raw.get("operator_name"), raw.get("calleeName"), raw.get("callee_name"))
    )

    return {
        "ats_id": ats_id,
        "filename": filename,
        "call_start_time": start,
        "call_end_time": end,
        "caller_number": caller_number,
        "operator_number": operator_number,
        "duration": duration,
        "ats_status": ats_status,
        "direction": infer_direction(raw, operator_number=operator_number),
        "caller_name": caller_name,
        "operator_name": operator_name,
        "source": raw,
    }


def extract_transcript_words(stt_payload: Any) -> list[dict]:
    if isinstance(stt_payload, list):
        items = stt_payload
    elif isinstance(stt_payload, dict):
        items = (
            stt_payload.get("words")
            or stt_payload.get("items")
            or stt_payload.get("data")
            or stt_payload.get("transcript")
            or []
        )
    else:
        items = []
    words: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        word = _as_str(item.get("word"))
        if not word:
            continue
        words.append(
            {
                "channel": _as_str(item.get("channel")) or "A",
                "startTime": float(item.get("startTime") or item.get("start_time") or 0),
                "endTime": float(item.get("endTime") or item.get("end_time") or 0),
                "word": word,
            }
        )
    return words


def format_mmss(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def words_to_turns(words: list[dict], *, gap_seconds: float = 1.2) -> list[dict]:
    """Group consecutive STT words on the same channel into dialogue turns."""
    turns: list[dict] = []
    current: Optional[dict] = None
    for item in words or []:
        channel = str(item.get("channel") or "A")
        word = str(item.get("word") or "").strip()
        if not word:
            continue
        start = float(item.get("startTime") or 0)
        end = float(item.get("endTime") or start)
        if (
            current is not None
            and current["channel"] == channel
            and start - current["end"] <= gap_seconds
        ):
            current["words"].append(word)
            current["end"] = max(current["end"], end)
            continue
        if current is not None:
            turns.append(_finalize_turn(current))
        current = {"channel": channel, "start": start, "end": end, "words": [word]}
    if current is not None:
        turns.append(_finalize_turn(current))
    return turns


def _finalize_turn(chunk: dict) -> dict:
    channel = chunk["channel"]
    speaker = "hr" if channel.upper() == "B" else "candidate"
    return {
        "at": format_mmss(chunk["start"]),
        "speaker": speaker,
        "text": " ".join(chunk["words"]),
        "channel": channel,
    }


def transcript_from_payload(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return extract_transcript_words(payload)
    if isinstance(payload, dict):
        return extract_transcript_words(payload.get("transcript") or payload.get("words") or payload)
    return []
