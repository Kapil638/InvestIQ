from unittest.mock import MagicMock, patch

from app.agents.llm import build_llm
from app.core.config import Settings


def test_build_llm_delegates_to_llm_factory() -> None:
    mock_llm = MagicMock()
    settings = Settings(openrouter_api_key="openrouter-key", llm_provider="openrouter")

    with patch("app.agents.llm.create_llm", return_value=mock_llm) as create_mock:
        result = build_llm(settings)

    assert result is mock_llm
    create_mock.assert_called_once_with(settings, skip_probe=False)
