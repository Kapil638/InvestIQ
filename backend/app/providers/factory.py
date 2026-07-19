"""Factory for financial data services and providers."""

from app.core.config import Settings
from app.providers.kite_mcp_provider import KiteMcpProvider
from app.providers.tapetide_mcp_provider import TapetideMcpProvider
from app.providers.yahoo_finance_provider import YahooFinanceProvider
from app.services.financial_data_service import FinancialDataService
from app.services.kite_auth_service import KiteAuthService
from app.services.kite_service import KiteService
from app.services.kite_token_store import get_kite_token_store
from app.services.tapetide_service import TapetideService
from app.services.company_master_service import get_company_master_service
from app.services.company_search_service import CompanySearchService
from app.services.symbol_resolver_service import get_symbol_resolver_service
from app.utils.exceptions import ConfigurationError


def build_financial_data_provider(settings: Settings) -> YahooFinanceProvider:
    if not settings.yfinance_enabled:
        raise ConfigurationError("YFINANCE_ENABLED must be true to collect financial data")
    return YahooFinanceProvider()


def build_kite_auth_service(settings: Settings) -> KiteAuthService:
    return KiteAuthService(settings=settings, token_store=get_kite_token_store())


def build_kite_service(settings: Settings) -> KiteService:
    yahoo = YahooFinanceProvider() if settings.yfinance_enabled else None
    auth_service = build_kite_auth_service(settings)
    return KiteService(
        settings=settings,
        provider=KiteMcpProvider(settings),
        yahoo_provider=yahoo,
        auth_service=auth_service,
    )


def build_tapetide_service(settings: Settings) -> TapetideService:
    yahoo = YahooFinanceProvider() if settings.yfinance_enabled else None
    return TapetideService(
        settings=settings,
        provider=TapetideMcpProvider(settings),
        yahoo_provider=yahoo,
    )


def build_company_search_service(settings: Settings) -> CompanySearchService:
    yahoo = YahooFinanceProvider() if settings.yfinance_enabled else None
    tapetide = build_tapetide_service(settings) if settings.tapetide_mcp_enabled else None
    master_service = get_company_master_service()
    master_service.ensure_loaded()
    symbol_resolver = get_symbol_resolver_service()
    symbol_resolver.ensure_loaded()
    return CompanySearchService(
        settings=settings,
        tapetide_service=tapetide,
        yahoo_provider=yahoo,
        master_service=master_service,
        symbol_resolver=symbol_resolver,
    )


def build_financial_data_service(settings: Settings) -> FinancialDataService:
    provider = build_financial_data_provider(settings)
    kite_service = build_kite_service(settings) if settings.kite_mcp_enabled else None
    tapetide_service = build_tapetide_service(settings) if settings.tapetide_mcp_enabled else None
    symbol_resolver = get_symbol_resolver_service()
    symbol_resolver.ensure_loaded()
    return FinancialDataService(
        provider=provider,
        kite_service=kite_service,
        tapetide_service=tapetide_service,
        symbol_resolver=symbol_resolver,
    )
