"""Shared helpers for advisor pipeline."""

from __future__ import annotations

import json
import re
from typing import Any

from app.utils.logging import get_logger

logger = get_logger(__name__)

_FORBIDDEN_PHRASES = (
    "buy now",
    "place order",
    "guaranteed return",
    "execute trade",
    "sell immediately",
)


def bare_symbol(symbol: str) -> str:
    return symbol.split(".")[0].strip().upper()


def as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def extract_json(text: str) -> dict[str, Any] | list[Any]:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    start_obj = cleaned.find("{")
    start_arr = cleaned.find("[")
    if start_arr >= 0 and (start_obj < 0 or start_arr < start_obj):
        end = cleaned.rfind("]")
        if start_arr >= 0 and end > start_arr:
            try:
                return json.loads(cleaned[start_arr : end + 1])
            except json.JSONDecodeError:
                pass
    start = start_obj
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    try:
        data = json.loads(cleaned)
        return data
    except json.JSONDecodeError:
        logger.warning("Advisor JSON parse failed")
        return {}


def sanitize_text_list(items: Any) -> list[str]:
    result: list[str] = []
    raw = as_str_list(items) if not isinstance(items, list) else [str(i) for i in items]
    for item in raw:
        lowered = item.lower()
        if any(p in lowered for p in _FORBIDDEN_PHRASES):
            item = item.replace("buy now", "worth researching").replace("place order", "further analysis")
        result.append(item)
    return result[:6]


def candidate_blob(*parts: str | None) -> str:
    return " ".join(p for p in parts if p).lower()
