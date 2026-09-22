"""Canonical RU phone matching for HR call lists."""
from __future__ import annotations

import re
from typing import Iterable, Optional

from sqlalchemy import and_, case, func, or_
from sqlalchemy.sql.elements import ColumnElement

from app import config

_NON_DIGITS = re.compile(r"\D+")


def digits_only(value: Optional[str]) -> str:
    return _NON_DIGITS.sub("", str(value or ""))


def canonical_ru_phone(value: Optional[str]) -> str:
    digits = digits_only(value)
    if len(digits) == 11 and digits.startswith("8"):
        return f"7{digits[1:]}"
    if len(digits) == 10:
        return f"7{digits}"
    return digits


def parse_phone_allowlist(raw: Optional[str] = None) -> frozenset[str]:
    text = (config.CALLS_ALLOWED_PHONES if raw is None else raw) or ""
    text = str(text).strip()
    if not text or text == "*":
        return frozenset()
    return frozenset(
        canonical_ru_phone(part)
        for part in text.split(",")
        if canonical_ru_phone(part)
    )


def call_involves_allowed_phones(
    caller_number: Optional[str],
    operator_number: Optional[str],
    allowed: Optional[Iterable[str]] = None,
) -> bool:
    allowed_set = (
        frozenset(canonical_ru_phone(item) for item in allowed if canonical_ru_phone(item))
        if allowed is not None
        else parse_phone_allowlist()
    )
    if not allowed_set:
        return True
    return (
        canonical_ru_phone(caller_number) in allowed_set
        or canonical_ru_phone(operator_number) in allowed_set
    )


def conversation_involves_allowed_phones(row, allowed: Optional[Iterable[str]] = None) -> bool:
    return call_involves_allowed_phones(
        getattr(row, "caller_number", None),
        getattr(row, "operator_number", None),
        allowed,
    )


def canonical_phone_sql(column) -> ColumnElement:
    digits = func.regexp_replace(func.coalesce(column, ""), "[^0-9]", "", "g")
    return case(
        (
            and_(func.length(digits) == 11, digits.like("8%")),
            func.concat("7", func.substr(digits, 2)),
        ),
        (func.length(digits) == 10, func.concat("7", digits)),
        else_=digits,
    )


def involved_phones_clause(caller_column, operator_column, allowed: Optional[Iterable[str]] = None):
    allowed_set = (
        frozenset(canonical_ru_phone(item) for item in allowed if canonical_ru_phone(item))
        if allowed is not None
        else parse_phone_allowlist()
    )
    if not allowed_set:
        return None
    values = list(allowed_set)
    return or_(
        canonical_phone_sql(caller_column).in_(values),
        canonical_phone_sql(operator_column).in_(values),
    )
