"""Psychometric scoring for complex work-profile assessment (new_test_info)."""
from __future__ import annotations

import json
import statistics
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.psychometrics.presentation import normalize_presentation, present_items


INSTRUMENTS_DIR = Path(__file__).resolve().parent / "instruments"


def _instrument_path(instrument_id: str) -> Path:
    direct = INSTRUMENTS_DIR / f"{instrument_id}.json"
    if direct.exists():
        return direct
    for path in INSTRUMENTS_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if instrument_id == data.get("id") or instrument_id in (data.get("aliases") or []):
            return path
    raise KeyError(f"Unknown instrument: {instrument_id}")


@lru_cache(maxsize=8)
def load_instrument(instrument_id: str) -> dict[str, Any]:
    path = _instrument_path(instrument_id)
    return json.loads(path.read_text(encoding="utf-8"))


def list_instruments_meta() -> list[dict[str, Any]]:
    items = []
    for path in sorted(INSTRUMENTS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        items.append(
            {
                "id": data["id"],
                "name": data["name"],
                "version": data.get("version"),
                "description": data.get("description"),
                "duration_minutes": data.get("duration_minutes"),
                "item_count": len(data.get("items") or []),
                "participant_fields": data.get("participant_fields") or [],
            }
        )
    return items


def public_instrument_payload(instrument_id: str) -> dict[str, Any]:
    """Safe payload for public take page (no scoring keys)."""
    data = load_instrument(instrument_id)
    public_items = []
    for it in data.get("items") or []:
        module = it.get("module")
        base = {
            "num": it["num"],
            "code": it["code"],
            "module": module,
        }
        if module == "disc":
            base.update({"prompt": it.get("prompt"), "options": it.get("options") or {}})
        elif module == "avp":
            base.update({"text": it.get("text")})
        elif module == "sjt":
            base.update(
                {
                    "title": it.get("title"),
                    "prompt": it.get("prompt"),
                    "options": it.get("options") or {},
                }
            )
        public_items.append(base)
    presentation = normalize_presentation(data.get("presentation"))
    return {
        "id": data["id"],
        "name": data["name"],
        "version": data.get("version"),
        "description": data.get("description"),
        "duration_minutes": data.get("duration_minutes"),
        "answer_scale": data.get("answer_scale"),
        "participant_fields": data.get("participant_fields") or [],
        "instruction": data.get("instruction"),
        "presentation": presentation,
        "items": present_items(public_items, presentation, shuffle=False),
    }


def _index_items(items: list[dict[str, Any]]) -> tuple[dict[str, dict], dict[str, dict]]:
    by_code = {it["code"]: it for it in items}
    by_num = {str(it["num"]): it for it in items}
    return by_code, by_num


def _lookup_answer(answers: dict[str, Any], item: dict[str, Any]) -> Any:
    return answers.get(item["code"], answers.get(str(item["num"])))


def _choice(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, int) and 1 <= value <= 4:
        return "ABCD"[value - 1]
    text = str(value).strip().upper()
    return text if text in {"A", "B", "C", "D"} else None


def _disc_pair(raw: Any) -> tuple[str | None, str | None]:
    if isinstance(raw, dict):
        return _choice(raw.get("most") or raw.get("answer_primary")), _choice(
            raw.get("least") or raw.get("answer_secondary")
        )
    return None, None


def _avp_raw(raw: Any) -> int | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if 1 <= value <= 5 else None


def _leading_name(rows: list[dict[str, Any]], score_key: str = "score") -> str | None:
    scored = [r for r in rows if r.get(score_key) is not None]
    if not scored:
        return None
    best = max(scored, key=lambda r: (r.get(score_key) or 0, -scored.index(r)))
    return best.get("name") or best.get("code")


def score_complex_profile(
    answers: dict[str, Any],
    instrument: dict[str, Any] | None = None,
    timing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = instrument or load_instrument("complex_work_profile")
    items = data["items"]
    by_code, _ = _index_items(items)
    answers = answers or {}
    timing = timing or {}
    thr = data.get("quality_thresholds") or {}

    filled = 0
    disc_logic_errors = 0
    avp_values: list[int] = []
    parsed: dict[str, Any] = {}

    for item in items:
        raw = _lookup_answer(answers, item)
        module = item["module"]
        if module == "disc":
            most, least = _disc_pair(raw)
            ok = bool(most and least and most != least)
            if most and least and most == least:
                disc_logic_errors += 1
            if ok:
                filled += 1
                parsed[item["code"]] = {"most": most, "least": least}
        elif module == "avp":
            value = _avp_raw(raw)
            if value is not None:
                filled += 1
                avp_values.append(value)
                adj = (6 - value) if int(item.get("reverse") or 0) == 1 else value
                parsed[item["code"]] = {"raw": value, "adjusted": adj}
        elif module == "sjt":
            choice = _choice(raw if not isinstance(raw, dict) else raw.get("choice") or raw.get("most"))
            if choice:
                filled += 1
                parsed[item["code"]] = {"choice": choice}

    expected = int(thr.get("expected_items") or len(items))
    missing = max(0, expected - filled)

    aspects_out = []
    aspect_index: dict[str, float | None] = {}
    for aspect in data.get("avp_aspects") or []:
        scale_items = [it for it in items if it.get("aspect_code") == aspect["code"]]
        adjusted = [
            parsed[it["code"]]["adjusted"]
            for it in scale_items
            if it["code"] in parsed
        ]
        complete = len(adjusted) == 8
        mean_adj = (sum(adjusted) / 8) if complete else None
        index = round((mean_adj - 1) / 4 * 100, 2) if mean_adj is not None else None
        aspect_index[aspect["code"]] = index
        aspects_out.append(
            {
                "code": aspect["code"],
                "name": aspect["name"],
                "answered": len(adjusted),
                "score": index,
                "status": "полный" if complete else "неполный",
            }
        )

    factors_out = []
    for factor in data.get("avp_factors") or []:
        a1, a2 = factor["aspects"]
        i1, i2 = aspect_index.get(a1), aspect_index.get(a2)
        if i1 is None or i2 is None:
            score = None
        elif factor.get("invert"):
            score = round(100 - (i1 + i2) / 2, 2)
        else:
            score = round((i1 + i2) / 2, 2)
        factors_out.append({"code": factor["code"], "name": factor["name"], "score": score})

    contexts = ["В работе", "Под давлением", "Личное"]
    disc_by_context: dict[str, list[dict[str, Any]]] = {}
    for context in contexts:
        ctx_items = [it for it in items if it.get("module") == "disc" and it.get("context") == context]
        complete = all(it["code"] in parsed for it in ctx_items) and len(ctx_items) == 8
        rows = []
        for letter in ("D", "I", "S", "C"):
            if not complete:
                rows.append({"code": letter, "name": letter, "raw": None, "score": None})
                continue
            raw_score = 0
            for it in ctx_items:
                pair = parsed[it["code"]]
                cats = it.get("categories") or {}
                if cats.get(pair["most"]) == letter:
                    raw_score += 1
                if cats.get(pair["least"]) == letter:
                    raw_score -= 1
            rows.append(
                {
                    "code": letter,
                    "name": letter,
                    "raw": raw_score,
                    "score": round((raw_score + 8) / 16 * 100, 2),
                }
            )
        disc_by_context[context] = rows

    paei_meta = {m["code"]: m["name"] for m in data.get("paei") or []}
    sjt_items = [it for it in items if it.get("module") == "sjt"]
    sjt_complete = all(it["code"] in parsed for it in sjt_items) and len(sjt_items) == 24
    role_counts = {code: 0 for code in ("P", "A", "E", "I")}
    sjt_sum = 0
    if sjt_complete:
        for it in sjt_items:
            choice = parsed[it["code"]]["choice"]
            prio = str((it.get("priorities") or {}).get(choice) or "")
            if prio in role_counts:
                role_counts[prio] += 1
            sjt_sum += int((it.get("scores") or {}).get(choice) or 0)
    # drop empty-key count if any
    paei_out = []
    for code in ("P", "A", "E", "I"):
        count = role_counts.get(code, 0) if sjt_complete else None
        paei_out.append(
            {
                "code": code,
                "name": paei_meta.get(code, code),
                "count": count,
                "score": round(count / 24 * 100, 2) if count is not None else None,
            }
        )
    sjt_quality = round(sjt_sum / 72 * 100, 2) if sjt_complete else None

    latencies = []
    raw_lat = timing.get("latencies_ms") or {}
    if isinstance(raw_lat, dict):
        for value in raw_lat.values():
            try:
                latencies.append(float(value))
            except (TypeError, ValueError):
                continue
    active = timing.get("active_duration_sec")
    wall = timing.get("wall_duration_sec")
    try:
        active_f = float(active) if active is not None and active != "" else None
    except (TypeError, ValueError):
        active_f = None
    try:
        wall_f = float(wall) if wall is not None and wall != "" else None
    except (TypeError, ValueError):
        wall_f = None

    rapid_share = None
    if latencies:
        rapid_ms = float(thr.get("rapid_answer_ms") or 1500)
        rapid_share = sum(1 for x in latencies if x < rapid_ms) / len(latencies)
    avp_sd = statistics.stdev(avp_values) if len(avp_values) >= 2 else None

    critical_sec = float(thr.get("critical_speed_sec") or 480)
    warning_sec = float(thr.get("warning_speed_sec") or 900)
    one_min = float(thr.get("one_minute_wall_sec") or 70)
    rapid_warn = float(thr.get("rapid_share_warning") or 0.25)
    sd_warn = float(thr.get("avp_low_variance_sd") or 0.25)

    if active_f is None and wall_f is None:
        speed_flag = "Ожидает данные"
    elif (active_f is not None and active_f < critical_sec) or (
        wall_f is not None and wall_f < one_min
    ):
        speed_flag = "Критическая проверка"
    elif (active_f is not None and active_f < warning_sec) or (
        rapid_share is not None and rapid_share > rapid_warn
    ):
        speed_flag = "Осторожно"
    else:
        speed_flag = "Без флага"

    low_var = avp_sd is not None and len(avp_values) == 80 and avp_sd < sd_warn
    if missing > 0:
        status = "Недостаточно данных"
    elif disc_logic_errors:
        status = "Критическая проверка"
    elif speed_flag == "Критическая проверка":
        status = "Критическая проверка"
    elif speed_flag == "Осторожно" or low_var:
        status = "Осторожно"
    else:
        status = "Приемлемый протокол"

    work_disc = disc_by_context.get("В работе") or []
    return {
        "instrument_id": data["id"],
        "instrument_version": data.get("version"),
        "scoring_version": data.get("scoring_version"),
        "quality": {
            "filled": filled,
            "missing_answers": missing,
            "disc_logic_errors": disc_logic_errors,
            "avp_sd": round(avp_sd, 4) if avp_sd is not None else None,
            "rapid_share": round(rapid_share, 4) if rapid_share is not None else None,
            "active_duration_sec": active_f,
            "wall_duration_sec": wall_f,
            "speed_flag": speed_flag,
            "status": status,
        },
        "avp": {"aspects": aspects_out, "factors": factors_out},
        "behavior_preferences": disc_by_context,
        "management_focus_distribution": paei_out,
        "sjt": {"sum": sjt_sum if sjt_complete else None, "max": 72, "quality_index": sjt_quality},
        "summary": {
            "quality_status": status,
            "behavior_preference": _leading_name(work_disc),
            "management_focus": _leading_name(paei_out),
            "work_style_focus": _leading_name(aspects_out),
        },
        "answered_count": filled,
        "total_items": expected,
        # Back-compat keys for older HR tables
        "scales": aspects_out,
        "work10": aspects_out,
    }


def score_instrument(
    answers: dict[str, Any],
    instrument: dict[str, Any],
    timing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return score_complex_profile(answers, instrument, timing)


# Back-compat name used by older tests / call sites
def score_complex_220(answers, instrument=None, timing=None):
    return score_complex_profile(answers, instrument, timing)
