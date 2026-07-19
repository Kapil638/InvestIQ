"""Classify OpenRouter LLM errors for retry and fallback decisions."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMErrorInfo:
    status_code: int | None
    message: str
    retryable: bool


_NON_RETRYABLE_STATUS_CODES = frozenset({400, 401, 402, 403, 404, 422})
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def _iter_exception_chain(exc: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        if current.__cause__ is not None:
            current = current.__cause__
        elif current.__context__ is not None:
            current = current.__context__
        else:
            break


def _status_from_message(message: str) -> int | None:
    match = re.search(r"\b(400|401|402|403|404|422|429|500|502|503|504)\b", message)
    if match:
        return int(match.group(1))
    lowered = message.lower()
    if "resource_exhausted" in lowered or "rate limit" in lowered:
        return 429
    if "bad gateway" in lowered:
        return 502
    if "gateway timeout" in lowered:
        return 504
    if "unavailable" in lowered or "overloaded" in lowered:
        return 503
    if "internal server error" in lowered:
        return 500
    if "unauthenticated" in lowered or "invalid authentication" in lowered:
        return 401
    if "invalid api key" in lowered or "api key not valid" in lowered:
        return 401
    if "requires more credits" in lowered or "insufficient" in lowered and "credit" in lowered:
        return 402
    if "invalid model" in lowered or ("not found" in lowered and "model" in lowered):
        return 404
    if "validation" in lowered or ("invalid" in lowered and "prompt" in lowered):
        return 422
    return None


def extract_http_status(exc: BaseException) -> int | None:
    for linked in _iter_exception_chain(exc):
        for attr in ("status_code", "http_status", "code"):
            value = getattr(linked, attr, None)
            if isinstance(value, int):
                return value

        response = getattr(linked, "response", None)
        if response is not None and hasattr(response, "status_code"):
            return int(response.status_code)

        status = _status_from_message(str(linked))
        if status is not None:
            return status

    return None


def classify_llm_error(exc: BaseException) -> LLMErrorInfo:
    status_code = extract_http_status(exc)
    message = str(exc).strip() or type(exc).__name__

    if status_code in _RETRYABLE_STATUS_CODES:
        return LLMErrorInfo(status_code=status_code, message=message, retryable=True)

    if status_code in _NON_RETRYABLE_STATUS_CODES:
        return LLMErrorInfo(status_code=status_code, message=message, retryable=False)

    inferred = _status_from_message(message)
    if inferred in _RETRYABLE_STATUS_CODES:
        return LLMErrorInfo(status_code=inferred, message=message, retryable=True)
    if inferred in _NON_RETRYABLE_STATUS_CODES:
        return LLMErrorInfo(status_code=inferred, message=message, retryable=False)

    return LLMErrorInfo(status_code=status_code, message=message, retryable=False)
