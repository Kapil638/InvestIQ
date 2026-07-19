from app.llm.errors import classify_llm_error, extract_http_status
from app.llm.models import default_fallback_models


def test_default_fallback_models_order() -> None:
    models = default_fallback_models()
    assert models == [
        "openai/gpt-4o-mini",
        "openai/gpt-4.1-mini",
        "google/gemini-2.5-flash",
        "anthropic/claude-3.5-haiku",
        "deepseek/deepseek-chat",
    ]


def test_classify_quota_error_as_retryable() -> None:
    info = classify_llm_error(Exception("429 rate limit exceeded"))
    assert info.retryable is True
    assert info.status_code == 429


def test_classify_bad_gateway_as_retryable() -> None:
    info = classify_llm_error(Exception("502 Bad Gateway"))
    assert info.retryable is True
    assert info.status_code == 502


def test_classify_service_unavailable_as_retryable() -> None:
    info = classify_llm_error(Exception("503 Service Unavailable"))
    assert info.retryable is True
    assert info.status_code == 503


def test_classify_gateway_timeout_as_retryable() -> None:
    info = classify_llm_error(Exception("504 Gateway Timeout"))
    assert info.retryable is True
    assert info.status_code == 504


def test_classify_auth_error_as_non_retryable() -> None:
    info = classify_llm_error(Exception("401 UNAUTHENTICATED invalid authentication"))
    assert info.retryable is False
    assert info.status_code == 401


def test_classify_invalid_model_as_non_retryable() -> None:
    info = classify_llm_error(Exception("404 model not found"))
    assert info.retryable is False
    assert info.status_code == 404


def test_extract_http_status_from_message() -> None:
    assert extract_http_status(Exception("upstream failed with 500")) == 500
