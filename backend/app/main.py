"""
FastAPI application entry point.

Architecture note:
- main.py only wires the app together (routes, middleware, lifespan).
- Business logic lives in services/, agents/, and tools/ – never here.
- This keeps the entry point thin and testable.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.exception_handlers import register_exception_handlers
from app.api.routes import (
    advisor,
    financials,
    google_drive_auth,
    health,
    kite,
    market,
    portfolio,
    reports,
    research,
    search,
    tapetide,
)
from app.api.dependencies import init_storage_services
from app.core.config import Settings, log_startup_config, reload_settings
from app.providers.factory import (
    build_company_search_service,
    build_financial_data_service,
    build_kite_service,
    build_tapetide_service,
)
from app.services.portfolio_holdings_service import PortfolioHoldingsService
from app.services.symbol_resolver_service import get_symbol_resolver_service
from app.services.company_master_service import get_company_master_service
from app.services.symbol_resolver_service import get_symbol_resolver_service
from app.utils.logging import setup_logging
from app.utils.timing import SLOW_THRESHOLD_SECONDS


from app.utils.logging import get_logger

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory – used by uvicorn and tests."""
    app_settings = settings or reload_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Startup/shutdown hooks – DB pools, ChromaDB, etc."""
        setup_logging(app_settings.log_level)
        log_startup_config(app_settings)
        get_company_master_service().ensure_loaded()
        get_symbol_resolver_service().ensure_loaded()
        app.state.settings = app_settings
        app.state.financial_data_service = build_financial_data_service(app_settings)
        app.state.company_search_service = build_company_search_service(app_settings)
        app.state.tapetide_service = build_tapetide_service(app_settings)
        app.state.portfolio_holdings_service = PortfolioHoldingsService(
            kite_service=build_kite_service(app_settings),
            symbol_resolver=get_symbol_resolver_service(),
        )
        if app_settings.storage_enabled:
            storage, rag = init_storage_services(app_settings)
            app.state.report_storage = storage
            app.state.rag_service = rag
        yield

    app = FastAPI(
        title=app_settings.app_name,
        version=__version__,
        description="AI-powered investment research platform",
        lifespan=lifespan,
        docs_url="/docs" if app_settings.debug else None,
        redoc_url="/redoc" if app_settings.debug else None,
    )
    app.state.settings = app_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.middleware("http")
    async def request_timing_middleware(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        if elapsed >= SLOW_THRESHOLD_SECONDS:
            logger.warning(
                "SLOW HTTP %s %s %.2fs",
                request.method,
                request.url.path,
                elapsed,
            )
        return response

    app.include_router(health.router, prefix=app_settings.api_prefix)
    app.include_router(financials.router, prefix=app_settings.api_prefix)
    app.include_router(tapetide.router, prefix=app_settings.api_prefix)
    app.include_router(market.router, prefix=app_settings.api_prefix)
    app.include_router(kite.router, prefix=app_settings.api_prefix)
    app.include_router(portfolio.router, prefix=app_settings.api_prefix)
    app.include_router(research.router, prefix=app_settings.api_prefix)
    app.include_router(reports.router, prefix=app_settings.api_prefix)
    app.include_router(search.router, prefix=app_settings.api_prefix)
    app.include_router(advisor.router, prefix=app_settings.api_prefix)
    app.include_router(google_drive_auth.router, prefix=app_settings.api_prefix)

    return app


app = create_app()
