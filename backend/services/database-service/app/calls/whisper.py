"""WhisperAi: map a call transcript to HR status + one-line description."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from app.db.v1.enums import CallConversationStatus
from app.t2.mapping import transcript_from_payload, words_to_turns

HR_STATUSES = (
    CallConversationStatus.interested.value,
    CallConversationStatus.interview.value,
    CallConversationStatus.callback.value,
    CallConversationStatus.rejected.value,
    CallConversationStatus.dropped.value,
)

_STATUS_ALIASES = {
    "interested": CallConversationStatus.interested.value,
    "интерес": CallConversationStatus.interested.value,
    "interview": CallConversationStatus.interview.value,
    "собеседование": CallConversationStatus.interview.value,
    "собес": CallConversationStatus.interview.value,
    "callback": CallConversationStatus.callback.value,
    "перезвон": CallConversationStatus.callback.value,
    "rejected": CallConversationStatus.rejected.value,
    "отказ": CallConversationStatus.rejected.value,
    "dropped": CallConversationStatus.dropped.value,
    "сброс": CallConversationStatus.dropped.value,
}

_UNANSWERED_ATS = frozenset(
    {
        "NOT_ANSWERED",
        "NOT_ANSWERED_COMMON",
        "MISSED",
        "NO_ANSWER",
        "BUSY",
        "CANCELLED",
        "CANCELED",
        "FAILED",
    }
)

WHISPER_SYSTEM_PROMPT = """Ты WhisperAi — классификатор HR-звонков для рекрутинга (вахта, линия, удалёнка, офис).
Тебе дают диалог: HR — оператор (канал B), кандидат — собеседник (канал A).

Верни ТОЛЬКО JSON-объект с полями:
{"status":"<код>","description":"<одна фраза>"}

status — ровно одно из:
interested — Интерес: кандидат в диалоге, уточняет условия, не отказал и не назначил собес/перезвон.
interview — Собеседование: договорились о встрече/собесе/медкомиссии, или перенесли уже назначенную встречу.
callback — Перезвон: попросили перезвонить в конкретное время/после события, сейчас не могут говорить.
rejected — Отказ: кандидат не подходит или сам отказался (смены, выезды, график, зарплата, «не интересно»).
dropped — Сброс: трубку бросили, тишина, автоответчик, ошиблись номером, разговора по сути не было.

Не используй pending / Определяется.

description — одна короткая фраза для HR на русском, как заметка в карточке.
Стиль (копируй тон, не копируй факты чужих звонков):
- Перенос вчерашней встречи на 12:00 из-за медкомиссии.
- Перезвон: уточняла удалёнку. Попросила перезвонить после 18:00.
- Отказ: не готов к ночным сменам и выездам на линию.

Правила описания:
- факты только из диалога (время, причина, условие);
- можно начинать с «Перезвон:» / «Отказ:» / «Сброс:», если это исход;
- без кавычек, без markdown, без списков, 1–2 предложения, до 180 символов;
- заканчивай точкой.

Если речи почти нет — dropped и «Сброс: разговор не состоялся.»
"""


def map_status(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip().lower().replace("ё", "е")
    text = text.split(":")[0].split(",")[0].strip()
    text = text.strip(" .")
    return _STATUS_ALIASES.get(text)


def normalize_description(raw: Any, *, status: str) -> str:
    text = " ".join(str(raw or "").split())
    text = text.strip(" \"'`")
    if len(text) > 180:
        text = text[:177].rstrip() + "…"
    if not text:
        fallback = {
            CallConversationStatus.interested.value: "Интерес: кандидат уточнял условия вакансии.",
            CallConversationStatus.interview.value: "Собеседование: договорились о встрече.",
            CallConversationStatus.callback.value: "Перезвон: кандидат попросил связаться позже.",
            CallConversationStatus.rejected.value: "Отказ: кандидат не готов к условиям вакансии.",
            CallConversationStatus.dropped.value: "Сброс: разговор не состоялся.",
        }
        text = fallback.get(status, "Исход звонка зафиксирован.")
    if text[-1] not in ".!?…":
        text += "."
    return text


def parse_whisper_payload(content: str) -> dict:
    raw = (content or "").strip()
    if not raw:
        raise ValueError("empty WhisperAi response")
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise ValueError("WhisperAi response is not JSON")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("WhisperAi JSON must be an object")
    status = map_status(data.get("status") or data.get("outcome") or data.get("label"))
    if status is None:
        raise ValueError(f"unknown WhisperAi status: {data.get('status')!r}")
    description = normalize_description(
        data.get("description") or data.get("summary") or data.get("note"),
        status=status,
    )
    return {"status": status, "description": description}


def dialogue_text(row: Any, *, max_chars: int = 12000) -> str:
    words = transcript_from_payload(getattr(row, "payload", None))
    turns = words_to_turns(words)
    lines: list[str] = []
    for turn in turns:
        speaker = "HR" if turn.get("speaker") == "hr" else "Кандидат"
        at = turn.get("at") or "00:00"
        text = (turn.get("text") or "").strip()
        if text:
            lines.append(f"[{at}] {speaker}: {text}")
    body = "\n".join(lines)
    if len(body) > max_chars:
        body = body[: max_chars - 1] + "…"
    return body


def is_unanswered_ats(ats_status: Optional[str]) -> bool:
    if not ats_status:
        return False
    return str(ats_status).strip().upper() in _UNANSWERED_ATS


def heuristic_without_transcript(
    row: Any,
    *,
    empty_as_dropped_seconds: int = 15,
) -> Optional[dict]:
    """Classify obvious non-talks locally so OpenAI is not called."""
    words = transcript_from_payload(getattr(row, "payload", None))
    if words:
        return None
    duration = getattr(row, "duration", None)
    ats_status = getattr(row, "ats_status", None)
    short = duration is not None and int(duration) <= empty_as_dropped_seconds
    if is_unanswered_ats(ats_status) or short:
        return {
            "status": CallConversationStatus.dropped.value,
            "description": "Сброс: разговор не состоялся.",
        }
    return None


def build_user_prompt(row: Any, *, max_chars: int = 12000) -> str:
    dialogue = dialogue_text(row, max_chars=max_chars)
    duration = getattr(row, "duration", None)
    ats = getattr(row, "ats_status", None) or "—"
    direction = getattr(row, "direction", None) or "—"
    if not dialogue.strip():
        dialogue = "(транскрипт пустой)"
    return (
        f"Длительность, сек: {duration if duration is not None else '—'}\n"
        f"Статус АТС: {ats}\n"
        f"Направление: {direction}\n"
        f"Диалог:\n{dialogue}"
    )
