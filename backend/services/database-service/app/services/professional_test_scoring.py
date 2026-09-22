"""Score and normalize professional (Q&A) public test submissions."""
from __future__ import annotations

from typing import Any


VIOLATION_MOUSE_LEAVE = "mouse_leave"
VIOLATION_TAB_BLUR = "tab_blur"


def _as_answer_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if raw is None:
        return {}
    return {"value": str(raw).strip()}


def normalize_public_answers(
    raw_answers: dict[str, Any],
    questions: list[Any],
) -> tuple[dict[str, Any], int, int]:
    """
    Build persisted answers + score from client payload.

    Client sends per question:
      { value?, option_index?, violations?: ["mouse_leave"|"tab_blur"], forced_incorrect? }
    or legacy plain string.

    Correctness is computed server-side from question.correct_option_index.
    Any integrity violation → forced incorrect (is_correct=False).
    """
    by_id = {str(q.id): q for q in (questions or []) if getattr(q, "id", None) is not None}
    scored = 0
    max_score = 0
    out: dict[str, Any] = {}

    for qid, question in by_id.items():
        payload = _as_answer_dict(raw_answers.get(qid))
        options = list(getattr(question, "options", None) or [])
        correct_idx = getattr(question, "correct_option_index", None)

        violations = [
            str(v)
            for v in (payload.get("violations") or [])
            if v in {VIOLATION_MOUSE_LEAVE, VIOLATION_TAB_BLUR}
        ]
        forced = bool(payload.get("forced_incorrect")) or bool(violations)

        option_index = payload.get("option_index")
        if option_index is not None:
            try:
                option_index = int(option_index)
            except (TypeError, ValueError):
                option_index = None

        value = payload.get("value")
        if value is None and option_index is not None and 0 <= option_index < len(options):
            value = options[option_index]
        value = str(value).strip() if value is not None else ""

        is_correct: bool | None = None
        if correct_idx is not None and options:
            max_score += 1
            if forced:
                is_correct = False
            elif option_index is None:
                is_correct = False
            else:
                is_correct = option_index == int(correct_idx)
            if is_correct:
                scored += 1
        elif forced:
            is_correct = False

        if not value and not forced and option_index is None:
            continue

        out[qid] = {
            "value": value or None,
            "option_index": option_index,
            "is_correct": is_correct,
            "forced_incorrect": forced,
            "violations": violations,
        }

    return out, scored, max_score


def professional_test_passed(
    score: int | None,
    max_score: int | None,
    *,
    timed_out: bool = False,
) -> bool:
    """Scored MCQ must be fully correct; open-ended completion counts as pass unless timed out."""
    if timed_out:
        return False
    if not max_score:
        return True
    return int(score or 0) >= int(max_score)


def public_question_dto(question: Any) -> dict[str, Any]:
    """Public take DTO — never expose correct_option_index."""
    options = list(getattr(question, "options", None) or [])
    return {
        "id": question.id,
        "text": question.text,
        "options": [str(o) for o in options if str(o).strip()],
    }
