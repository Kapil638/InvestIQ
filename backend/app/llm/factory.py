"""Factory for LLM instances used by CrewAI agents."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.llm.manager import LLMManager
from app.llm.openrouter import OPENROUTER_PROVIDER
from app.utils.exceptions import ConfigurationError


def create_llm(settings: Settings, *, skip_probe: bool = False) -> Any:
    """Return the configured LLM for all CrewAI agents."""
    provider = settings.llm_provider.strip().lower()

    if provider == OPENROUTER_PROVIDER:
        if not settings.openrouter_api_key:
            raise ConfigurationError("OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter")
        return LLMManager(settings).acquire(skip_probe=skip_probe)

    raise ConfigurationError(
        f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. "
        f"Set LLM_PROVIDER={OPENROUTER_PROVIDER} in backend/.env"
    )
