from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.llm.manager import LLMManager
from app.llm.openrouter import create_openrouter_llm
from app.utils.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def clear_llm_cache() -> None:
    from app.llm import manager as llm_manager

    llm_manager._LLM_CACHE.clear()
    yield
    llm_manager._LLM_CACHE.clear()


@pytest.fixture
def openrouter_settings() -> Settings:
    return Settings(
        openrouter_api_key="openrouter-key",
        llm_provider="openrouter",
        openrouter_model="openai/gpt-4o-mini",
        llm_retry_backoff_seconds="0,0",
    )


def test_acquire_returns_first_successful_llm(openrouter_settings: Settings) -> None:
    mock_llm = MagicMock()
    with (
        patch("app.llm.manager.create_openrouter_llm", return_value=mock_llm),
        patch.object(LLMManager, "_probe"),
    ):
        llm = LLMManager(openrouter_settings).acquire()

    assert llm is mock_llm


def test_acquire_retries_on_429_then_succeeds(openrouter_settings: Settings) -> None:
    mock_llm = MagicMock()
    probe = MagicMock(side_effect=[Exception("429 rate limit"), None])

    with (
        patch("app.llm.manager.create_openrouter_llm", return_value=mock_llm),
        patch.object(LLMManager, "_probe", probe),
        patch("app.llm.manager.time.sleep") as sleep_mock,
    ):
        llm = LLMManager(openrouter_settings).acquire()

    assert llm is mock_llm
    assert probe.call_count == 2
    sleep_mock.assert_called_once_with(0)


def test_acquire_retries_on_502_then_succeeds(openrouter_settings: Settings) -> None:
    mock_llm = MagicMock()
    probe = MagicMock(side_effect=[Exception("502 Bad Gateway"), None])

    with (
        patch("app.llm.manager.create_openrouter_llm", return_value=mock_llm),
        patch.object(LLMManager, "_probe", probe),
        patch("app.llm.manager.time.sleep"),
    ):
        llm = LLMManager(openrouter_settings).acquire()

    assert llm is mock_llm


def test_acquire_skips_non_retryable_auth_error_and_falls_back() -> None:
    settings = Settings(
        openrouter_api_key="openrouter-key",
        llm_provider="openrouter",
        llm_retry_backoff_seconds="0,0",
    )
    first_llm = MagicMock()
    second_llm = MagicMock()
    create_mock = MagicMock(side_effect=[first_llm, second_llm])
    probe = MagicMock(
        side_effect=[
            Exception("401 UNAUTHENTICATED invalid authentication"),
            None,
        ]
    )

    with (
        patch("app.llm.manager.create_openrouter_llm", create_mock),
        patch.object(LLMManager, "_probe", probe),
        patch("app.llm.manager.time.sleep"),
    ):
        llm = LLMManager(settings).acquire()

    assert llm is second_llm
    assert create_mock.call_count == 2


def test_acquire_raises_when_all_models_fail(openrouter_settings: Settings) -> None:
    with (
        patch(
            "app.llm.manager.create_openrouter_llm",
            side_effect=Exception("401 UNAUTHENTICATED"),
        ),
        patch("app.llm.manager.time.sleep"),
        pytest.raises(ConfigurationError, match="All OpenRouter models failed"),
    ):
        LLMManager(openrouter_settings).acquire()


def test_custom_fallback_models_from_settings() -> None:
    settings = Settings(
        openrouter_api_key="openrouter-key",
        llm_provider="openrouter",
        llm_fallback_models="openai/gpt-4.1,deepseek/deepseek-chat-v3",
        llm_retry_backoff_seconds="0",
    )
    mock_llm = MagicMock()

    with (
        patch("app.llm.manager.create_openrouter_llm", return_value=mock_llm) as create_mock,
        patch.object(LLMManager, "_probe"),
    ):
        llm = LLMManager(settings).acquire()

    assert llm is mock_llm
    create_mock.assert_called_once_with(settings, "openai/gpt-4.1")


def test_create_openrouter_llm_requires_api_key() -> None:
    settings = Settings(openrouter_api_key=None)
    with pytest.raises(ConfigurationError, match="OPENROUTER_API_KEY"):
        create_openrouter_llm(settings, "openai/gpt-4.1-mini")
