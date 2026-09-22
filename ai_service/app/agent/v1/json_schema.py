"""Prepare Pydantic JSON Schema for OpenAI structured outputs (strict)."""
from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel


_STRIP_KEYS = frozenset({"title", "description", "examples", "example", "default", "deprecated"})


def openai_json_schema(model: Type[BaseModel]) -> dict[str, Any]:
    """Return a JSON Schema OpenAI accepts with ``strict: true``.

    Pydantic schemas include ``$defs``, optional ``anyOf``/null, and
    ``additionalProperties`` defaults that OpenAI rejects.
    """
    raw = model.model_json_schema()
    defs = raw.pop("$defs", None) or raw.pop("definitions", {}) or {}
    return _normalize(_resolve_refs(raw, defs))


def _resolve_refs(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_resolve_refs(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str):
        name = ref.rsplit("/", 1)[-1]
        resolved = defs.get(name, {})
        merged = {**_resolve_refs(resolved, defs), **{k: v for k, v in node.items() if k != "$ref"}}
        return _resolve_refs(merged, defs)
    return {key: _resolve_refs(value, defs) for key, value in node.items()}


def _normalize(node: Any) -> Any:
    if isinstance(node, list):
        return [_normalize(item) for item in node]
    if not isinstance(node, dict):
        return node

    is_schema_node = any(
        key in node for key in ("type", "properties", "anyOf", "oneOf", "$ref", "items", "additionalProperties")
    )
    if is_schema_node:
        cleaned = {k: _normalize(v) for k, v in node.items() if k not in _STRIP_KEYS}
    else:
        cleaned = {k: _normalize(v) for k, v in node.items()}

    if cleaned.get("type") == "object" or "properties" in cleaned:
        props = cleaned.get("properties") or {}
        cleaned["type"] = "object"
        cleaned["properties"] = {name: _normalize(schema) for name, schema in props.items()}
        cleaned["additionalProperties"] = False
        cleaned["required"] = list(cleaned["properties"].keys())
        return cleaned

    if "anyOf" in cleaned or "oneOf" in cleaned:
        variants = cleaned.get("anyOf") or cleaned.get("oneOf") or []
        non_null = [item for item in variants if not (isinstance(item, dict) and item.get("type") == "null")]
        has_null = len(non_null) < len(variants)
        if len(non_null) == 1 and has_null:
            merged = dict(non_null[0])
            merged["type"] = [merged.get("type", "string"), "null"] if isinstance(merged.get("type"), str) else merged.get("type")
            if isinstance(merged.get("type"), str):
                merged["type"] = [merged["type"], "null"]
            extra = {k: v for k, v in cleaned.items() if k not in ("anyOf", "oneOf")}
            extra.update(merged)
            return _normalize(extra)

    return cleaned
