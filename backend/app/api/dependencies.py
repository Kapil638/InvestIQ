"""FastAPI dependency injection providers."""

from fastapi import Depends, Request

from app.core.config import Settings, reload_settings
from app.utils.exceptions import ConfigurationError, SessionRequiredError
from app.database.factory import create_report_repository, create_user_repository, create_vector_store
from app.database.repositories.base import UserRepository
from app.providers.factory import (
    build_financial_data_service,
    build_google_drive_auth_service,
    build_kite_auth_service,
    build_kite_service,
    build_company_search_service,
    build_tapetide_service,
)
from app.services.google_drive_auth_service import GoogleDriveAuthService
from app.services.kite_auth_service import KiteAuthService
from app.services.financial_data_service import FinancialDataService
from app.services.kite_service import KiteService
from app.services.company_search_service import CompanySearchService
from app.services.tapetide_service import TapetideService
from app.services.portfolio_analyze_service import PortfolioAnalyzeService
from app.services.portfolio_holdings_service import PortfolioHoldingsService
from app.services.symbol_resolver_service import get_symbol_resolver_service
from app.services.rag_service import RagService
from app.services.report_chat_service import ReportChatService
from app.services.report_export_service import ReportExportService
from app.services.report_storage_service import ReportStorageService
from app.services.google_drive_service import GoogleDriveService
from app.services.owner_auth_service import OwnerAuthService, OwnerSessionData, SESSION_COOKIE_NAME
from app.services.advisor_service import AdvisorService
from app.services.research_ask_service import ResearchAskService
from app.services.research_crew_service import ResearchCrewService


def resolve_settings(request: Request) -> Settings:
    """Return settings attached to the app at startup."""
    cfg = getattr(request.app.state, "settings", None)
    if cfg is None:
        raise ConfigurationError("Application settings are not initialized")
    return cfg


def get_kite_auth_service(
    settings: Settings = Depends(resolve_settings),
) -> KiteAuthService:
    return build_kite_auth_service(settings)


def get_google_drive_auth_service(
    settings: Settings = Depends(resolve_settings),
) -> GoogleDriveAuthService:
    return build_google_drive_auth_service(settings)


def get_kite_service(
    settings: Settings = Depends(resolve_settings),
) -> KiteService:
    return build_kite_service(settings)


def get_tapetide_service(
    request: Request,
    settings: Settings = Depends(resolve_settings),
) -> TapetideService:
    svc = getattr(request.app.state, "tapetide_service", None)
    if svc is None:
        svc = build_tapetide_service(settings)
    return svc


def get_company_search_service(
    request: Request,
    settings: Settings = Depends(resolve_settings),
) -> CompanySearchService:
    svc = getattr(request.app.state, "company_search_service", None)
    if svc is None:
        svc = build_company_search_service(settings)
    return svc


def get_financial_data_service(
    request: Request,
    settings: Settings = Depends(resolve_settings),
) -> FinancialDataService:
    svc = getattr(request.app.state, "financial_data_service", None)
    if svc is None:
        svc = build_financial_data_service(settings)
    return svc


def get_research_ask_service(
    settings: Settings = Depends(resolve_settings),
    financial_service: FinancialDataService = Depends(get_financial_data_service),
) -> ResearchAskService:
    return ResearchAskService(settings=settings, financial_service=financial_service)


def get_research_crew_service(
    request: Request,
    settings: Settings = Depends(resolve_settings),
) -> ResearchCrewService:
    return ResearchCrewService(settings=settings)


def _build_report_storage(settings: Settings) -> ReportStorageService:
    repository = create_report_repository(settings)
    vector_store = create_vector_store(settings)
    return ReportStorageService(repository=repository, vector_store=vector_store)


def get_report_chat_service(
    request: Request,
    settings: Settings = Depends(resolve_settings),
) -> ReportChatService:
    storage = get_report_storage_service(request)
    rag: RagService | None = None
    try:
        rag = get_rag_service(request)
    except Exception:
        rag = None
    return ReportChatService(settings=settings, storage=storage, rag_service=rag)


def get_report_storage_service(request: Request) -> ReportStorageService:
    storage = getattr(request.app.state, "report_storage", None)
    if storage is None:
        settings = resolve_settings(request)
        storage = _build_report_storage(settings)
    return storage


def get_user_repository(request: Request) -> UserRepository:
    """Cached on app.state at startup (see init_storage_services).

    IMPORTANT: must stay cached, not rebuilt per-request — a fresh
    InMemoryUserRepository per call would silently lose all owner/credential
    data immediately (see create_user_repository's docstring).
    """
    repo = getattr(request.app.state, "user_repository", None)
    if repo is None:
        settings = resolve_settings(request)
        repo = create_user_repository(settings)
    return repo


def get_owner_auth_service(
    settings: Settings = Depends(resolve_settings),
    user_repo: UserRepository = Depends(get_user_repository),
) -> OwnerAuthService:
    return OwnerAuthService(settings=settings, user_repo=user_repo)


async def require_owner_session(
    request: Request,
    settings: Settings = Depends(resolve_settings),
    owner_auth: OwnerAuthService = Depends(get_owner_auth_service),
) -> OwnerSessionData:
    """Real server-side enforcement for the owner-auth gate.

    Self-disabling: when ALLOWED_OWNER_EMAILS is unset (owner_auth_configured is
    False), every route stays open exactly as before this gate existed.
    """
    if not settings.owner_auth_configured:
        return OwnerSessionData(owner_id="dev-bypass", email="dev@local")

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise SessionRequiredError("Sign-in required.")

    session = owner_auth.verify_session_token(token)
    if session is None:
        raise SessionRequiredError("Session expired or invalid. Please sign in again.")

    return session


def get_google_drive_service(
    settings: Settings = Depends(resolve_settings),
) -> GoogleDriveService:
    return GoogleDriveService(settings=settings)


def get_report_export_service(
    request: Request,
    settings: Settings = Depends(resolve_settings),
) -> ReportExportService:
    storage = get_report_storage_service(request)
    drive = GoogleDriveService(settings=settings)
    return ReportExportService(storage=storage, drive_service=drive)


def get_portfolio_holdings_service(
    request: Request,
    settings: Settings = Depends(resolve_settings),
) -> PortfolioHoldingsService:
    svc = getattr(request.app.state, "portfolio_holdings_service", None)
    if svc is None:
        svc = PortfolioHoldingsService(
            kite_service=build_kite_service(settings),
            symbol_resolver=get_symbol_resolver_service(),
        )
    return svc


def get_advisor_service(
    request: Request,
    settings: Settings = Depends(resolve_settings),
    financial_service: FinancialDataService = Depends(get_financial_data_service),
    search_service: CompanySearchService = Depends(get_company_search_service),
    holdings_service: PortfolioHoldingsService = Depends(get_portfolio_holdings_service),
) -> AdvisorService:
    storage = getattr(request.app.state, "report_storage", None)
    rag: RagService | None = getattr(request.app.state, "rag_service", None)
    return AdvisorService(
        settings=settings,
        financial_service=financial_service,
        search_service=search_service,
        holdings_service=holdings_service,
        report_storage=storage,
        rag_service=rag,
    )


def get_portfolio_analyze_service(
    settings: Settings = Depends(resolve_settings),
    financial_service: FinancialDataService = Depends(get_financial_data_service),
) -> PortfolioAnalyzeService:
    return PortfolioAnalyzeService(settings=settings, financial_data_service=financial_service)


def get_rag_service(request: Request) -> RagService:
    rag = getattr(request.app.state, "rag_service", None)
    if rag is None:
        settings = resolve_settings(request)
        vector_store = create_vector_store(settings)
        rag = RagService(vector_store=vector_store)
    return rag


def init_storage_services(settings: Settings) -> tuple[ReportStorageService, RagService]:
    """Initialize storage services for app lifespan."""
    vector_store = create_vector_store(settings)
    storage = ReportStorageService(
        repository=create_report_repository(settings),
        vector_store=vector_store,
    )
    rag = RagService(vector_store=vector_store)
    return storage, rag


def init_user_repository(settings: Settings) -> UserRepository:
    """Initialize the owner-user repository once for app lifespan (see
    get_user_repository's docstring for why this must not be rebuilt per-request)."""
    return create_user_repository(settings)
