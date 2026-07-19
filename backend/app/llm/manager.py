"""LLM Manager – OpenRouter fallback chain, retries, and structured logging."""

from __future__ import annotations

import time
from typing import Any

from app.core.config import Settings
from app.llm.errors import classify_llm_error
from app.llm.openrouter import OPENROUTER_PROVIDER, create_openrouter_llm
from app.utils.exceptions import ConfigurationError
from app.utils.logging import get_logger

logger = get_logger(__name__)

_PROBE_PROMPT = "Reply with exactly: OK"

# Process-wide cache: skip repeated health probes within TTL (seconds)
_LLM_CACHE: dict[str, tuple[Any, float]] = {}
_LLM_CACHE_TTL = 300.0


class LLMManager:
    """Acquire a working CrewAI LLM via OpenRouter with model fallback."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def acquire(self, *, skip_probe: bool = False) -> Any:
        """Return the first OpenRouter-backed LLM that passes the health probe."""
        cache_key = self._cache_key()
        cached = _LLM_CACHE.get(cache_key)
        if cached and time.monotonic() < cached[1]:
            logger.debug("LLM cache hit provider=%s", OPENROUTER_PROVIDER)
            return cached[0]

        if not self._settings.openrouter_api_key:
            raise ConfigurationError("OPENROUTER_API_KEY is required for AI research")

        models = self._settings.resolved_llm_model_chain()
        if not models:
            raise ConfigurationError("LLM fallback model chain is empty")

        backoff_seconds = self._settings.llm_retry_backoff_seconds_tuple
        failures: list[str] = []

        for model in models:
            if skip_probe and cached and cached[0] is not None:
                llm = create_openrouter_llm(self._settings, model)
                _LLM_CACHE[cache_key] = (llm, time.monotonic() + _LLM_CACHE_TTL)
                return llm

            llm, error = self._try_model_with_retries(model, backoff_seconds, probe=not skip_probe)
            if llm is not None:
                _LLM_CACHE[cache_key] = (llm, time.monotonic() + _LLM_CACHE_TTL)
                crewai_model = getattr(llm, "model", model)
                logger.info(
                    "LLM acquired provider=%s model=%s crewai_model=%s",
                    OPENROUTER_PROVIDER,
                    model,
                    crewai_model,
                )
                return llm

            if error:
                failures.append(error)

        detail = "; ".join(failures) if failures else "No models available"
        raise ConfigurationError(f"All OpenRouter models failed. {detail}")

    def _cache_key(self) -> str:
        chain = ",".join(self._settings.resolved_llm_model_chain())
        return f"{OPENROUTER_PROVIDER}:{chain}"

    def _try_model_with_retries(
        self,
        model: str,
        backoff_seconds: tuple[int, ...],
        *,
        probe: bool = True,
    ) -> tuple[Any | None, str | None]:
        max_attempts = len(backoff_seconds) + 1

        for attempt in range(1, max_attempts + 1):
            started = time.perf_counter()
            try:
                llm = create_openrouter_llm(self._settings, model)
                if probe:
                    self._probe(llm)
            except Exception as exc:
                response_time_ms = int((time.perf_counter() - started) * 1000)
                error_info = classify_llm_error(exc)
                logger.warning(
                    "LLM probe failed provider=%s model=%s retry_count=%d "
                    "error_code=%s response_time_ms=%d message=%s",
                    OPENROUTER_PROVIDER,
                    model,
                    attempt,
                    error_info.status_code,
                    response_time_ms,
                    error_info.message,
                )

                if not error_info.retryable:
                    return None, (
                        f"{model}: {error_info.status_code or 'error'} – {error_info.message}"
                    )

                if attempt >= max_attempts:
                    return None, (
                        f"{model}: exhausted retries after "
                        f"{error_info.status_code or 'transient error'}"
                    )

                delay = backoff_seconds[attempt - 1]
                logger.info(
                    "Retrying LLM probe provider=%s model=%s retry_count=%d delay_s=%d",
                    OPENROUTER_PROVIDER,
                    model,
                    attempt + 1,
                    delay,
                )
                time.sleep(delay)
                continue

            response_time_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "LLM probe succeeded provider=%s model=%s retry_count=%d response_time_ms=%d",
                OPENROUTER_PROVIDER,
                model,
                attempt,
                response_time_ms,
            )
            return llm, None

        return None, f"{model}: unknown failure"

    @staticmethod
    def _probe(llm: Any) -> None:
        llm.call(_PROBE_PROMPT)
