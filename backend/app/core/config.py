"""
Centralized application configuration using Pydantic Settings.

All environment variables are loaded here once and consumed via:

    from app.core.config import settings
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Resolve backend/.env regardless of process working directory
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _BACKEND_DIR / ".env"


def _is_kite_credential_set(value: str | None) -> bool:
    """True when a non-empty Kite credential is present (not a .env placeholder)."""
    if not value or not value.strip():
        return False
    normalized = value.strip()
    if normalized.startswith("<") and normalized.endswith(">"):
        return False
    if "PASTE_" in normalized.upper():
        return False
    return True


def _is_tapetide_token_set(value: str | None) -> bool:
    """True when a non-empty Tapetide token is present (not a .env placeholder)."""
    return _is_kite_credential_set(value)


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "InvestIQ"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # LLM – OpenRouter (unified provider)
    llm_provider: str = "openrouter"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4o-mini"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_fallback_models: str | None = None
    llm_fallback_chain: str | None = None  # legacy alias for llm_fallback_models JSON
    llm_retry_backoff_seconds: str = "3,8"

    # CORS – comma-separated origins
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Guardrails
    guardrail_collection_max_age_hours: int = 24
    guardrail_statement_max_age_months: int = 18
    guardrail_news_max_age_days: int = 30
    guardrail_max_analysis_retries: int = 1
    guardrail_block_on_warnings: bool = False

    # Financial data
    yfinance_enabled: bool = True
    fmp_api_key: str | None = None

    # Kite MCP – read-only market data & portfolio (no order placement)
    kite_mcp_enabled: bool = False
    kite_mcp_url: str = "https://mcp.kite.trade/mcp"
    kite_mcp_read_only: bool = True
    kite_excluded_tools: str = (
        "place_order,modify_order,cancel_order,place_gtt_order,modify_gtt_order,delete_gtt_order"
    )
    kite_api_key: str | None = None
    kite_api_secret: str | None = None
    kite_redirect_url: str = "http://127.0.0.1:8002/api/v1/kite/callback"
    kite_frontend_redirect_url: str = "http://localhost:5173/portfolio"

    # NSE/BSE MCP – deprecated (use Tapetide MCP instead)
    nse_bse_mcp_enabled: bool = False
    nse_bse_mcp_url: str = "http://localhost:3000/mcp"
    nse_bse_mcp_read_only: bool = True
    nse_bse_mcp_timeout_seconds: int = 20

    # Tapetide MCP – read-only Indian exchange data (npx -y tapetide-mcp or remote)
    tapetide_mcp_enabled: bool = False
    tapetide_mcp_url: str = "https://mcp.tapetide.com/mcp"
    tapetide_api_token: str | None = None
    tapetide_mcp_read_only: bool = True
    tapetide_mcp_timeout_seconds: int = 20

    # Google Drive API – report PDF export
    google_drive_enabled: bool = False
    google_drive_root_folder_id: str | None = None

    # Service account path – kept for Workspace/Shared Drive setups; personal Gmail
    # accounts cannot use this (service accounts have no storage quota of their own).
    google_drive_service_account_file: str | None = None
    google_drive_service_account_json: str | None = None

    # OAuth user delegation – required for personal Gmail accounts. Uploads count
    # against the authenticated user's own Drive quota. Tokens stay server-side.
    google_drive_oauth_client_id: str | None = None
    google_drive_oauth_client_secret: str | None = None
    google_drive_oauth_redirect_url: str = "http://127.0.0.1:8002/api/v1/google-drive/callback"
    google_drive_oauth_frontend_redirect_url: str = "http://localhost:5173/reports"

    # Owner authentication gate – single-owner allowlist + session signing.
    # Self-disabling: when ALLOWED_OWNER_EMAILS is unset, the gate no-ops and every
    # route stays open (see owner_auth_configured / require_owner_session).
    allowed_owner_emails: str | None = None
    session_secret_key: str | None = None
    session_max_age_days: int = 30

    # Google Sign-In (owner login identity) – a separate OAuth Client ID from
    # GOOGLE_DRIVE_OAUTH_CLIENT_ID. Sign-In uses Google Identity Services (ID-token
    # flow, "Authorized JavaScript origins"); Drive uses the authorization-code
    # redirect flow. They are not interchangeable.
    google_signin_client_id: str | None = None

    # WebAuthn / passkey (platform authenticator unlock) – local dev only for now.
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "InvestIQ"
    webauthn_origin: str = "http://localhost:5173"

    # Search
    tavily_api_key: str | None = None

    # Database & storage
    supabase_url: str | None = None
    supabase_anon_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "supabase_anon_key",
            "SUPABASE_ANON_KEY",
            "supabase_key",
            "SUPABASE_KEY",
        ),
    )
    chroma_enabled: bool = True
    chroma_persist_directory: str = "./chroma_data"
    chroma_collection_name: str = "research_reports"
    storage_enabled: bool = True

    # Logging & cache
    log_level: str = "INFO"
    cache_enabled: bool = False
    cache_ttl_seconds: int = 300

    # CrewAI
    crew_verbose: bool = False
    crew_memory: bool = False

    # Limits
    max_news_results: int = 10
    max_document_chunks: int = 20
    max_search_results: int = 10

    @field_validator("chroma_persist_directory")
    @classmethod
    def strip_chroma_directory(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_environment_rules(self) -> Self:
        if self.is_production and self.debug:
            raise ValueError("DEBUG must be false when APP_ENV=production")

        if self.chroma_enabled and not self.chroma_persist_directory:
            raise ValueError(
                "CHROMA_PERSIST_DIRECTORY must not be empty when CHROMA_ENABLED=true"
            )

        return self

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def uses_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def kite_excluded_tools_list(self) -> list[str]:
        return [part.strip() for part in self.kite_excluded_tools.split(",") if part.strip()]

    @property
    def kite_oauth_configured(self) -> bool:
        """True when both Kite API key and secret are set (values never logged)."""
        return _is_kite_credential_set(self.kite_api_key) and _is_kite_credential_set(
            self.kite_api_secret
        )

    @property
    def tapetide_token_configured(self) -> bool:
        """True when Tapetide API token is set (value never logged)."""
        return _is_tapetide_token_set(self.tapetide_api_token)

    @property
    def google_drive_oauth_configured(self) -> bool:
        """True when both Drive OAuth client id and secret are set (values never logged)."""
        return _is_kite_credential_set(self.google_drive_oauth_client_id) and _is_kite_credential_set(
            self.google_drive_oauth_client_secret
        )

    @property
    def allowed_owner_emails_list(self) -> list[str]:
        return [e.strip().lower() for e in (self.allowed_owner_emails or "").split(",") if e.strip()]

    @property
    def owner_auth_configured(self) -> bool:
        """True when the owner-auth gate is turned on (allowlist non-empty).

        When False, require_owner_session no-ops and every route stays open —
        this is what keeps adding auth from breaking any existing behavior until
        ALLOWED_OWNER_EMAILS is explicitly set.
        """
        return bool(self.allowed_owner_emails_list)

    @property
    def google_signin_configured(self) -> bool:
        return _is_kite_credential_set(self.google_signin_client_id)

    @property
    def llm_retry_backoff_seconds_tuple(self) -> tuple[int, ...]:
        values = [
            int(part.strip())
            for part in self.llm_retry_backoff_seconds.split(",")
            if part.strip()
        ]
        if not values:
            return (3, 8)
        return tuple(values)

    def _parse_model_chain_value(self, raw: str) -> list[str]:
        from app.llm.openrouter import normalize_openrouter_model_id

        stripped = raw.strip()
        if not stripped:
            return []

        if stripped.startswith("["):
            parsed = json.loads(stripped)
            if not isinstance(parsed, list):
                raise ValueError("LLM fallback models must be a JSON array")
            models: list[str] = []
            for item in parsed:
                if isinstance(item, str):
                    models.append(normalize_openrouter_model_id(item))
                elif isinstance(item, dict):
                    provider = str(item.get("provider", "")).strip().lower()
                    model = str(item.get("model", "")).strip()
                    if not model:
                        continue
                    if provider == "gemini":
                        models.append(normalize_openrouter_model_id(f"gemini/{model}"))
                    else:
                        models.append(normalize_openrouter_model_id(model))
            return [model for model in models if model]

        return [
            normalize_openrouter_model_id(part.strip())
            for part in stripped.split(",")
            if part.strip()
        ]

    def resolved_llm_model_chain(self) -> list[str]:
        """Return the ordered OpenRouter model fallback chain."""
        override = self.llm_fallback_models or self.llm_fallback_chain
        if override:
            return self._parse_model_chain_value(override)

        from app.llm.models import default_fallback_models

        models = default_fallback_models()
        if self.openrouter_model:
            return [self.openrouter_model] + [
                model for model in models if model != self.openrouter_model
            ]
        return models

    def resolved_llm_fallback_chain(self) -> list[dict[str, str]]:
        """Backward-compatible view for startup logging."""
        return [
            {"provider": "openrouter", "model": model}
            for model in self.resolved_llm_model_chain()
        ]


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process from backend/.env."""
    return Settings()


def reload_settings() -> Settings:
    """Force reload from disk – use after .env changes or at app startup."""
    get_settings.cache_clear()
    return get_settings()


# Backward-compatible alias
settings = get_settings()


def log_startup_config(app_settings: Settings | None = None) -> None:
    """Log non-sensitive configuration summary at application startup."""
    cfg = app_settings or get_settings()

    logger.info("Starting %s", cfg.app_name)
    logger.info("Environment: %s", cfg.app_env)
    logger.info("Debug mode: %s", cfg.debug)
    logger.info("Chroma enabled: %s", cfg.chroma_enabled)
    logger.info("Storage enabled: %s", cfg.storage_enabled)
    logger.info("Tavily configured: %s", bool(cfg.tavily_api_key))
    logger.info("Kite enabled: %s", cfg.kite_mcp_enabled)
    logger.info("Kite OAuth configured: %s", cfg.kite_oauth_configured)
    logger.info("Kite read-only: %s", cfg.kite_mcp_read_only)
    logger.info("NSE/BSE MCP enabled: %s", cfg.nse_bse_mcp_enabled)
    logger.info("NSE/BSE MCP read-only: %s", cfg.nse_bse_mcp_read_only)
    logger.info("Tapetide MCP enabled: %s", cfg.tapetide_mcp_enabled)
    logger.info("Tapetide MCP read-only: %s", cfg.tapetide_mcp_read_only)
    logger.info("Tapetide token configured: %s", cfg.tapetide_token_configured)
    logger.info("Google Drive enabled: %s", cfg.google_drive_enabled)
    logger.info("Google Drive OAuth configured: %s", cfg.google_drive_oauth_configured)
    logger.info("Owner auth gate enabled: %s", cfg.owner_auth_configured)
    if cfg.owner_auth_configured and not _is_kite_credential_set(cfg.session_secret_key):
        logger.warning(
            "SESSION_SECRET_KEY not set — using an ephemeral secret; "
            "all sessions will be invalidated on every restart"
        )
    logger.info("LLM provider: %s", cfg.llm_provider)
    logger.info("LLM configured: %s", bool(cfg.openrouter_api_key))
    logger.info("LLM selected model: %s", cfg.openrouter_model)
    logger.info("OpenRouter base URL: %s", cfg.openrouter_base_url)
    logger.info(
        "LLM fallback chain: %s",
        ", ".join(cfg.resolved_llm_model_chain()),
    )

    if cfg.storage_enabled and not cfg.uses_supabase:
        if cfg.is_production:
            logger.warning(
                "STORAGE_ENABLED=true but SUPABASE_URL and SUPABASE_ANON_KEY are not configured"
            )
        else:
            logger.warning(
                "STORAGE_ENABLED=true but Supabase is not configured; using in-memory fallback"
            )
