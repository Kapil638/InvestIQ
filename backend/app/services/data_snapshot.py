"""Canonical data snapshot hashing for report stability checks."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.schemas.financial import FinancialResearchResponse
from app.schemas.news import NewsResearchResponse


def _strip_volatile(obj: Any) -> Any:
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for key, value in obj.items():
            if key in {"collected_at", "generated_at", "created_at", "data_timestamp"}:
                continue
            cleaned[key] = _strip_volatile(value)
        return cleaned
    if isinstance(obj, list):
        return [_strip_volatile(item) for item in obj]
    return obj


def compute_data_snapshot_hash(
    ticker: str,
    financial_data: FinancialResearchResponse | None,
    news_data: NewsResearchResponse | None,
) -> str:
    payload = {
        "ticker": ticker.strip().upper(),
        "financial": financial_data.model_dump(mode="json") if financial_data else None,
        "news": news_data.model_dump(mode="json") if news_data else None,
    }
    canonical = json.dumps(_strip_volatile(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
