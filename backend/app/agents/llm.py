"""CrewAI LLM configuration for InvestIQ agents."""

from typing import Any

from app.core.config import Settings
from app.llm.factory import create_llm


def build_llm(settings: Settings, *, skip_probe: bool = False) -> Any:
    """
    Acquire the primary LLM for CrewAI agents.

    All agents must use this entry point rather than instantiating provider LLMs directly.
    """
    return create_llm(settings, skip_probe=skip_probe)
