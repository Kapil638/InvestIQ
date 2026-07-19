"""Configuration models for the OpenRouter LLM fallback chain."""

from __future__ import annotations


def default_fallback_models() -> list[str]:
    """Built-in OpenRouter model fallback order for InvestIQ."""
    return [
        "openai/gpt-4o-mini",
        "openai/gpt-4.1-mini",
        "google/gemini-2.5-flash",
        "anthropic/claude-3.5-haiku",
        "deepseek/deepseek-chat",
    ]
