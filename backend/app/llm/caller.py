"""OpenRouter LLM invocation with transient retry and timeout handling."""

from __future__ import annotations

import time
from typing import Any

from app.core.config import Settings
from app.llm.errors import classify_llm_error
from app.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS = 90
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def call_llm_with_retry(
    llm: Any,
    prompt: str,
    *,
    settings: Settings | None = None,
    label: str = "llm_call",
) -> str:
    """Call CrewAI LLM with retries only for transient provider errors."""
    from app.core.config import get_settings

    cfg = settings or get_settings()
    backoff = cfg.llm_retry_backoff_seconds_tuple
    max_attempts = len(backoff) + 1
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        started = time.perf_counter()
        try:
            result = llm.call(prompt)
            elapsed = time.perf_counter() - started
            if elapsed >= 2.0:
                logger.warning("SLOW %s completed in %.2fs attempt=%d", label, elapsed, attempt)
            if isinstance(result, str):
                return result
            return str(result)
        except Exception as exc:
            elapsed = time.perf_counter() - started
            info = classify_llm_error(exc)
            last_error = exc
            logger.warning(
                "%s failed attempt=%d code=%s retryable=%s elapsed=%.2fs msg=%s",
                label,
                attempt,
                info.status_code,
                info.retryable,
                elapsed,
                info.message,
            )
            if not info.retryable or info.status_code not in RETRYABLE_STATUS:
                raise
            if attempt >= max_attempts:
                raise
            delay = backoff[attempt - 1]
            time.sleep(delay)

    if last_error:
        raise last_error
    raise RuntimeError(f"{label} failed without exception")
