"""Deterministic DOCX/PDF/ZIP generation for adaptation documents."""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from typing import Any, Iterable
from zipfile import ZIP_DEFLATED, ZipFile


SAFE_DOCUMENT_TYPES = frozenset({"manager_safe"})


def document_types_for_kind(kind: str, *, has_hr: bool = True) -> list[str]:
    if kind == "week_1":
        return ["employee_answers", "hr_comment", "internal_slice", "manager_safe"]
    if kind == "month_1":
        return ["employee_answers", "manager_answers", "hr_comment", "internal_slice", "manager_safe"]
    if kind == "month_2":
        return ["employee_answers", "manager_answers", "hr_comment", "internal_slice", "manager_safe", "conclusion"]
    if kind == "extra":
        result = ["employee_answers"]
        if has_hr:
            result.append("hr_comment")
        result.append("internal_slice")
        return result
    return []  # control route is present in period reporting without an artificial document


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", "_", str(value or "")).strip(" ._")
    return re.sub(r"\s+", " ", cleaned) or "Документ"


def render_filename(template: str, context: dict[str, Any], *, extension: str) -> str:
    class Vars(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    base = str(template or "{ФИО}_{Этап}_{Тип}_{Версия}").format_map(Vars(context))
    return f"{safe_filename(base)}.{extension.lower()}"


def _answer(row: dict, role: str) -> dict:
    return next((dict(item.get("payload") or {}) for item in row.get("answers") or [] if item.get("role") == role), {})


def _pretty_lines(payload: dict, kind: str = "", role: str = "") -> list[str]:
    from app.adaptation.catalog import form_for
    labels = {question["id"]: question["text"] for question in form_for(kind, role)}
    return [f"{labels.get(key, key)}: {value if not isinstance(value, list) else ', '.join(map(str, value))}" for key, value in payload.items()]


def _history_lines(row: dict) -> list[str]:
    from app.adaptation.catalog import CORE_EMPLOYEE_IDS
    from app.adaptation.rules import KIND_LABELS
    lines = []
    for stage in row.get("stage_history") or []:
        employee = _answer(stage, "employee")
        values = "; ".join(str(employee.get(key, "нет данных")) for key in CORE_EMPLOYEE_IDS)
        lines.append(f"{KIND_LABELS.get(stage['kind'], stage['kind'])}, факт {stage.get('fact_date') or 'не завершён'}: {values}")
    return lines or ["История: данных недостаточно"]


def document_lines(row: dict, document_type: str, signatures: Iterable[str] = ()) -> tuple[str, list[str]]:
    title_map = {
        "employee_answers": "Ответы сотрудника",
        "manager_answers": "Ответы руководителя",
        "hr_comment": "Комментарий HR",
        "internal_slice": "Внутренний срез адаптации",
        "manager_safe": "Безопасный отчёт руководителю",
        "conclusion": "Заключение об испытательном сроке",
    }
    title = title_map[document_type]
    base = [
        f"Сотрудник: {row.get('full_name') or '—'}",
        f"Должность: {row.get('position') or '—'}",
        f"Подразделение: {row.get('department') or '—'}",
        f"Этап: {row.get('kind_label') or row.get('kind') or '—'}",
        f"Плановая дата: {row.get('plan_date') or '—'}",
        f"Фактическая дата: {row.get('fact_date') or '—'}",
    ]
    if document_type == "employee_answers":
        lines = base + _pretty_lines(_answer(row, "employee"), row.get("kind"), "employee")
    elif document_type == "manager_answers":
        lines = base + _pretty_lines(_answer(row, "manager"), row.get("kind"), "manager")
    elif document_type == "hr_comment":
        lines = base + _pretty_lines(_answer(row, "hr"), row.get("kind"), "hr")
    elif document_type == "manager_safe":
        hr = _answer(row, "hr")
        lines = base + [
            f"Итог: {row.get('outcome') or '—'}",
            f"Риск: {row.get('risk_label') or row.get('risk') or '—'}",
            f"Комментарий: {hr.get('manager_summary') or '—'}",
            f"Рекомендации: {hr.get('hr_recommend') or '—'}",
            "Динамика пяти показателей без конфиденциальных комментариев:",
            *_history_lines(row),
        ]
    else:
        signals = row.get("risk_signals") or {}
        lines = base + [
            f"Итог: {row.get('outcome') or '—'}",
            f"Риск: {row.get('risk_label') or row.get('risk') or '—'}",
            f"Сильные сигналы: {', '.join(signals.get('strong') or []) or 'нет'}",
            f"Средние сигналы: {', '.join(signals.get('medium') or []) or 'нет'}",
        ]
        if document_type == "conclusion":
            lines.extend([
                "Основание: этапы и участники", *_history_lines(row),
                "Подтверждённые результаты и качество (источник: руководитель)",
                *(_pretty_lines(_answer(row, "manager"), row.get("kind"), "manager") or ["Данных руководителя недостаточно"]),
                "Решение и условия (источник: HR)",
                str(_answer(row, "hr").get("hr_comment") or "Решение HR не зафиксировано"),
            ])
        else:
            lines.extend([
                "Динамика пяти показателей (источник: сотрудник)", *_history_lines(row),
                "Освоение роли, результат и самостоятельность (источник: руководитель)",
                *(_pretty_lines(_answer(row, "manager"), row.get("kind"), "manager") or ["Данных руководителя недостаточно"]),
                "Контекст и оценка HR", str(_answer(row, "hr").get("hr_comment") or "Комментарий отсутствует"),
            ])
        lines.append("Действия и эффект сопровождения")
        for action in row.get("action_records") or []:
            lines.append(f"{action['action']}; ответственный: {action.get('owner') or 'не назначен'}; срок: {action.get('due_date') or 'не указан'}; статус: {action.get('status')}; эффект: {action.get('effect') or 'не оценён'}")
        if not row.get("action_records"):
            lines.append("Действия не зафиксированы; данных об эффекте недостаточно")
        if document_type == "conclusion":
            lines.extend(["", *[f"Подпись {role}: ____________________" for role in signatures], "Дата: ____________________"])
    return title, lines


def render_docx(title: str, lines: list[str], *, one_page: bool) -> bytes:
    from docx import Document
    from docx.shared import Cm, Pt

    document = Document()
    section = document.sections[0]
    section.page_height, section.page_width = Cm(29.7), Cm(21)
    section.top_margin = section.bottom_margin = Cm(1.25)
    section.left_margin = section.right_margin = Cm(1.5)
    heading = document.add_paragraph()
    heading.paragraph_format.space_after = Pt(6)
    run = heading.add_run(title)
    run.bold = True
    run.font.size = Pt(14)
    for line in lines:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(2 if one_page else 5)
        paragraph.paragraph_format.line_spacing = 0.9 if one_page else 1.0
        text_run = paragraph.add_run(str(line))
        text_run.font.size = Pt(8 if one_page else 10)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _font_path() -> str:
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("Cyrillic font is not installed (fonts-dejavu-core is required)")


def render_pdf(title: str, lines: list[str], *, one_page: bool) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import KeepInFrame, Paragraph, SimpleDocTemplate, Spacer

    font_name = "AdaptationSans"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, _font_path()))
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=32, bottomMargin=32)
    title_style = ParagraphStyle("title", fontName=font_name, fontSize=14, leading=17, spaceAfter=8)
    body_style = ParagraphStyle("body", fontName=font_name, fontSize=8.5 if one_page else 10, leading=10 if one_page else 13, alignment=TA_LEFT)
    story = [Paragraph(title, title_style)]
    body = [Paragraph(str(line).replace("&", "&amp;").replace("<", "&lt;"), body_style) for line in lines]
    if one_page:
        story.append(KeepInFrame(A4[0] - 72, A4[1] - 110, body, mode="shrink"))
    else:
        for item in body:
            story.extend([item, Spacer(1, 3)])
    doc.build(story)
    return stream.getvalue()


def render_document(row: dict, document_type: str, fmt: str, signatures: Iterable[str]) -> bytes:
    title, lines = document_lines(row, document_type, signatures)
    one_page = document_type in {"internal_slice", "manager_safe", "conclusion"}
    if fmt == "docx":
        return render_docx(title, lines, one_page=one_page)
    if fmt == "pdf":
        return render_pdf(title, lines, one_page=one_page)
    raise ValueError("Поддерживаются только DOCX и PDF")


def content_hash(content: bytes) -> str:
    return sha256(content).hexdigest()


def build_zip(files: Iterable[tuple[str, bytes]]) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        seen: set[str] = set()
        for name, content in files:
            candidate = name
            stem, dot, suffix = candidate.rpartition(".")
            index = 2
            while candidate.lower() in seen:
                candidate = f"{stem}_{index}{dot}{suffix}"
                index += 1
            seen.add(candidate.lower())
            archive.writestr(candidate, content)
    return stream.getvalue()
