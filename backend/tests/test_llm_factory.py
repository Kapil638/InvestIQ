from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.llm.factory import create_llm
from app.llm.openrouter import create_openrouter_llm
from app.utils.exceptions import ConfigurationError


def test_create_llm_requires_openrouter_provider() -> None:
    settings = Settings(llm_provider="gemini", openrouter_api_key="key")
    with pytest.raises(ConfigurationError, match="LLM_PROVIDER"):
        create_llm(settings)


def test_create_openrouter_llm_prefixes_model_for_crewai() -> None:
    settings = Settings(
        llm_provider="openrouter",
        openrouter_api_key="openrouter-key",
        openrouter_model="openai/gpt-4o-mini",
    )
    mock_llm = MagicMock()

    with patch("crewai.LLM", return_value=mock_llm) as llm_cls:
        result = create_openrouter_llm(settings, "openai/gpt-4o-mini")

    assert result is mock_llm
    llm_cls.assert_called_once()
    kwargs = llm_cls.call_args.kwargs
    assert "provider" not in kwargs
    assert kwargs["model"] == "openrouter/openai/gpt-4o-mini"
    assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
