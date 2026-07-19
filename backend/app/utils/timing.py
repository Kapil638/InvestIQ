"""Request timing helpers – log slow provider/service calls (>2s)."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Iterator

from app.utils.logging import get_logger

logger = get_logger(__name__)

SLOW_THRESHOLD_SECONDS = 2.0


@contextmanager
def timed_operation(name: str, **fields: Any) -> Iterator[None]:
    """Log duration for a sync block; warn when slower than threshold."""
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started
        _log_duration(name, elapsed, fields)


@asynccontextmanager
async def async_timed_operation(name: str, **fields: Any) -> AsyncIterator[None]:
    """Async variant of timed_operation."""
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started
        _log_duration(name, elapsed, fields)


def _log_duration(name: str, elapsed: float, fields: dict[str, Any]) -> None:
    safe_fields = {k: v for k, v in fields.items() if k not in {"token", "api_key", "secret"}}
    detail = " ".join(f"{k}={v}" for k, v in safe_fields.items())
    message = f"{name} completed in {elapsed:.2f}s"
    if detail:
        message = f"{message} ({detail})"
    if elapsed >= SLOW_THRESHOLD_SECONDS:
        logger.warning("SLOW %s", message)
    else:
        logger.debug("%s", message)
