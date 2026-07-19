from app.llm.openrouter import format_openrouter_model, normalize_openrouter_model_id


def test_normalize_legacy_gemini_model_to_google_openrouter_id() -> None:
    assert normalize_openrouter_model_id("gemini/gemini-2.5-flash") == "google/gemini-2.5-flash"


def test_normalize_strips_openrouter_prefix() -> None:
    assert normalize_openrouter_model_id("openrouter/openai/gpt-4o-mini") == "openai/gpt-4o-mini"


def test_format_openrouter_model_returns_crewai_model_string() -> None:
    assert format_openrouter_model("openai/gpt-4o-mini") == "openrouter/openai/gpt-4o-mini"
