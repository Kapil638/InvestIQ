import pytest
from pydantic import ValidationError

from app.core.config import Settings, log_startup_config, settings


def test_cors_origins_parsed_from_comma_separated_string() -> None:
    cfg = Settings(
        cors_origins="https://app.vercel.app, http://localhost:5173",
    )
    assert cfg.cors_origins_list == [
        "https://app.vercel.app",
        "http://localhost:5173",
    ]


def test_settings_singleton_loads_from_env() -> None:
    assert settings.app_name == "InvestIQ"
    assert settings.api_prefix == "/api/v1"


def test_supabase_legacy_key_alias_is_supported() -> None:
    cfg = Settings(
        supabase_url="https://example.supabase.co",
        SUPABASE_KEY="legacy-anon-key",
    )
    assert cfg.supabase_anon_key == "legacy-anon-key"
    assert cfg.uses_supabase is True


def test_production_debug_validation_fails() -> None:
    with pytest.raises(ValidationError, match="DEBUG must be false"):
        Settings(app_env="production", debug=True)


def test_chroma_directory_required_when_enabled() -> None:
    with pytest.raises(ValidationError, match="CHROMA_PERSIST_DIRECTORY"):
        Settings(chroma_enabled=True, chroma_persist_directory="   ")


def test_kite_oauth_configured_when_keys_present() -> None:
    cfg = Settings(kite_api_key="key", kite_api_secret="secret")
    assert cfg.kite_oauth_configured is True


def test_kite_oauth_not_configured_without_secret() -> None:
    cfg = Settings(kite_api_key="key", kite_api_secret=None)
    assert cfg.kite_oauth_configured is False


def test_kite_oauth_not_configured_with_placeholders() -> None:
    cfg = Settings(
        kite_api_key="<PASTE_KITE_API_KEY_HERE>",
        kite_api_secret="<PASTE_KITE_API_SECRET_HERE>",
    )
    assert cfg.kite_oauth_configured is False


def test_log_startup_config_does_not_raise() -> None:
    log_startup_config(Settings(app_env="test", debug=True, storage_enabled=False))


def test_resolved_llm_model_chain_uses_defaults() -> None:
    # openrouter_model is a required str (no None allowed) — pass the actual
    # default explicitly rather than omitting it, since omitting it would pick
    # up whatever OPENROUTER_MODEL happens to be set to in the real local .env,
    # defeating the point of testing the "no override" default-chain behavior.
    # llm_fallback_models must also be pinned to None: LLM_FALLBACK_MODELS
    # REPLACES the whole chain when set, and the real .env sets it (to the
    # free-tier Gemma chain), which would otherwise leak into this test.
    cfg = Settings(openrouter_model="openai/gpt-4o-mini", llm_fallback_models=None)
    chain = cfg.resolved_llm_model_chain()
    assert chain[0] == "openai/gpt-4o-mini"
    assert chain[-1] == "deepseek/deepseek-chat"


def test_resolved_llm_model_chain_normalizes_legacy_gemini_entries() -> None:
    cfg = Settings(
        llm_fallback_models='[{"provider":"gemini","model":"gemini-2.5-flash"}]',
    )
    assert cfg.resolved_llm_model_chain() == ["google/gemini-2.5-flash"]


def test_resolved_llm_model_chain_puts_openrouter_model_first() -> None:
    # See llm_fallback_models=None note above - same reason.
    cfg = Settings(openrouter_model="anthropic/claude-3.7-sonnet", llm_fallback_models=None)
    chain = cfg.resolved_llm_model_chain()
    assert chain[0] == "anthropic/claude-3.7-sonnet"


def test_llm_retry_backoff_seconds_tuple_parses_csv() -> None:
    cfg = Settings(llm_retry_backoff_seconds="3,8")
    assert cfg.llm_retry_backoff_seconds_tuple == (3, 8)
