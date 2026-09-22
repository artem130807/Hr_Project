"""How items are shown: block order and optional within-block shuffle.

Scoring always keys by item ``code``; this layer never changes keys or answers.
Canonical bank order remains disc → avp → sjt. Presentation 2-3-1 is
avp → sjt → disc. The original second block (AVP) is shuffled per take session.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable, Iterable, Optional

DEFAULT_BLOCK_ORDER = ("avp", "sjt", "disc")
DEFAULT_SHUFFLE_MODULES = ("avp",)


def imul32(a: int, b: int) -> int:
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF


def mulberry32(seed: int) -> Callable[[], float]:
    """Same sequence as the frontend ``mulberry32`` helper (uint32)."""
    state = seed & 0xFFFFFFFF

    def rng() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state
        t = imul32(t ^ (t >> 15), t | 1)
        t = (t ^ ((t + imul32(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rng


def normalize_presentation(raw: Optional[dict[str, Any]]) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    order = [str(m) for m in (data.get("block_order") or DEFAULT_BLOCK_ORDER) if m]
    shuffle = [str(m) for m in (data.get("shuffle_modules") or DEFAULT_SHUFFLE_MODULES) if m]
    if not order:
        order = list(DEFAULT_BLOCK_ORDER)
    return {
        "scheme": data.get("scheme") or "231",
        "block_order": order,
        "shuffle_modules": shuffle,
        "block_count": len(order),
        "blocks": data.get("blocks")
        or [
            {"module": "avp", "title": "Личностный профиль"},
            {"module": "sjt", "title": "Рабочие ситуации — внутренний SJT, пилотная версия"},
            {"module": "disc", "title": "Рабочие предпочтения — внутренний пилотный поведенческий блок"},
        ],
    }


def _shuffle(items: list[dict[str, Any]], rng: Callable[[], float]) -> list[dict[str, Any]]:
    out = list(items)
    for i in range(len(out) - 1, 0, -1):
        j = int(rng() * (i + 1))
        out[i], out[j] = out[j], out[i]
    return out


def present_items(
    items: Iterable[dict[str, Any]],
    presentation: Optional[dict[str, Any]] = None,
    *,
    seed: Optional[int] = None,
    shuffle: bool = True,
) -> list[dict[str, Any]]:
    """Reorder modules, optionally Fisher–Yates shuffle listed modules."""
    spec = normalize_presentation(presentation)
    groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for item in items:
        module = str(item.get("module") or "_")
        groups.setdefault(module, []).append(item)

    rng = mulberry32(int(seed) & 0xFFFFFFFF) if seed is not None else None
    if shuffle and rng is not None:
        for module in spec["shuffle_modules"]:
            if module in groups:
                groups[module] = _shuffle(groups[module], rng)

    out: list[dict[str, Any]] = []
    used: set[str] = set()
    for module in spec["block_order"]:
        if module in groups:
            out.extend(groups[module])
            used.add(module)
    for module, bucket in groups.items():
        if module not in used:
            out.extend(bucket)
    return out


def block_number(module: Optional[str], presentation: Optional[dict[str, Any]] = None) -> int:
    spec = normalize_presentation(presentation)
    try:
        return spec["block_order"].index(str(module)) + 1
    except ValueError:
        return spec["block_count"]
