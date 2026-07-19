"""LLM provider management for CrewAI agents."""

from app.llm.manager import LLMManager
from app.llm.models import default_fallback_models
from app.llm.openrouter import OPENROUTER_PROVIDER, create_openrouter_llm

__all__ = [
    "LLMManager",
    "OPENROUTER_PROVIDER",
    "create_openrouter_llm",
    "default_fallback_models",
]
