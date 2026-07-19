"""OpenRouter LLM wrapper for CrewAI agents."""

from __future__ import annotations

import os
from typing import Any

from app.core.config import Settings
from app.utils.exceptions import ConfigurationError
from app.utils.logging import get_logger

logger = get_logger(__name__)

OPENROUTER_PROVIDER = "openrouter"

# Legacy direct-provider keys that must not be used when routing via OpenRouter.
_BLOCKED_PROVIDER_ENV_KEYS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)


def normalize_openrouter_model_id(model: str) -> str:
    """
    Normalize configured model IDs to OpenRouter format.

    Converts legacy values like ``gemini/gemini-2.5-flash`` to
    ``google/gemini-2.5-flash`` and strips accidental ``openrouter/`` prefixes.
    """
    normalized = model.strip()
    if not normalized:
        raise ValueError("Model id must not be empty")

    if normalized.startswith("openrouter/"):
        normalized = normalized.removeprefix("openrouter/")

    if normalized.startswith("gemini/"):
        return f"google/{normalized.removeprefix('gemini/')}"

    return normalized


def format_openrouter_model(model: str) -> str:
    """Return the CrewAI OpenRouter model string (``openrouter/<model-id>``)."""
    return f"openrouter/{normalize_openrouter_model_id(model)}"


def _ensure_openrouter_environment(settings: Settings) -> None:
    """Configure process env for OpenRouter and disable direct provider SDK routing."""
    if not settings.openrouter_api_key:
        raise ConfigurationError("OPENROUTER_API_KEY is required for AI research")

    os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
    os.environ["OPENROUTER_BASE_URL"] = settings.openrouter_base_url

    for key in _BLOCKED_PROVIDER_ENV_KEYS:
        os.environ.pop(key, None)


def create_openrouter_llm(settings: Settings, model: str) -> Any:
    """
    Create a CrewAI LLM that always routes through OpenRouter.

    Uses CrewAI's OpenAI-compatible OpenRouter provider – never the Gemini SDK.
    """
    if settings.llm_provider != OPENROUTER_PROVIDER:
        raise ConfigurationError(
            f"LLM_PROVIDER must be '{OPENROUTER_PROVIDER}' (got '{settings.llm_provider}')"
        )

    _ensure_openrouter_environment(settings)

    from crewai import LLM

    router_model = f"openrouter/{normalize_openrouter_model_id(model)}"

    logger.info("LLM Provider: OpenRouter")
    logger.info("LLM Model: %s", router_model)
    logger.info("Base URL: %s", settings.openrouter_base_url)

    return LLM(
        model=router_model,
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )
