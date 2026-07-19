"""Per-stage pipeline output caching keyed by data snapshot hash."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.utils import ttl_cache

PIPELINE_NAMESPACE = "pipeline"
PIPELINE_TTL = 300


def _stage_key(stage: str, data_hash: str, *extra: str) -> str:
    parts = [stage, data_hash, *extra]
    return ":".join(parts)


def _content_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def get_stage(stage: str, data_hash: str, *extra: str) -> Any | None:
    return ttl_cache.get(PIPELINE_NAMESPACE, _stage_key(stage, data_hash, *extra))


def set_stage(stage: str, data_hash: str, value: Any, *extra: str) -> None:
    ttl_cache.NAMESPACE_TTL[PIPELINE_NAMESPACE] = PIPELINE_TTL
    ttl_cache.set(PIPELINE_NAMESPACE, _stage_key(stage, data_hash, *extra), value)


def cache_key_for_analysis(data_hash: str) -> str:
    return _stage_key("analysis", data_hash)


def cache_key_for_risk(data_hash: str, analysis_hash: str) -> str:
    return _stage_key("risk", data_hash, analysis_hash)


def cache_key_for_recommendation(data_hash: str, analysis_hash: str, risk_hash: str) -> str:
    return _stage_key("recommendation", data_hash, analysis_hash, risk_hash)


def hash_payload(payload: Any) -> str:
    return _content_hash(payload)
