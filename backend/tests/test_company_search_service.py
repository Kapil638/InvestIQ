"""Tests for company search service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.providers.data_sources import NSE_SOURCE, TAPETIDE_MCP_SOURCE, YAHOO_SOURCE
from app.services.company_master_service import CompanyMasterService
from app.services.company_search_service import CompanySearchService


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        debug=True,
        tapetide_mcp_enabled=True,
        tapetide_api_token="tpt_rt_test_token",
        yfinance_enabled=True,
    )


@pytest.fixture
def tapetide_service() -> MagicMock:
    service = MagicMock()
    service.search_stocks = AsyncMock()
    return service


@pytest.fixture
def yahoo_provider() -> MagicMock:
    provider = MagicMock()
    provider.search_companies = AsyncMock()
    return provider


@pytest.fixture
def master_service() -> CompanyMasterService:
    service = CompanyMasterService()
    service.ensure_loaded()
    return service


@pytest.mark.asyncio
async def test_search_uses_nse_master_first(settings, tapetide_service, yahoo_provider, master_service) -> None:
    from app.schemas.company_search import CompanySearchResult

    tapetide_service.search_stocks.return_value = [
        CompanySearchResult(
            symbol="INFY",
            exchange="NSE",
            company_name="Infosys Limited",
            sector="Information Technology",
            source=TAPETIDE_MCP_SOURCE,
        )
    ]
    yahoo_provider.search_companies.return_value = []
    service = CompanySearchService(settings, tapetide_service, yahoo_provider, master_service)

    response = await service.search("inf")

    assert response.source == NSE_SOURCE
    assert any(item.symbol == "INFY" for item in response.results)
    tapetide_service.search_stocks.assert_not_called()
    yahoo_provider.search_companies.assert_not_called()


@pytest.mark.asyncio
async def test_search_falls_back_to_yahoo_when_nse_empty(
    settings, tapetide_service, yahoo_provider, master_service
) -> None:
    tapetide_service.search_stocks.return_value = []
    yahoo_provider.search_companies.return_value = [
        {
            "symbol": "ZZZTEST",
            "exchange": "NSE",
            "company_name": "Zzz Test Corp",
            "sector": "Test",
        }
    ]
    service = CompanySearchService(settings, tapetide_service, yahoo_provider, master_service)

    response = await service.search("zzztestcorp")

    assert response.source == YAHOO_SOURCE
    assert response.fallback is True
    assert response.results[0].symbol == "ZZZTEST"
    tapetide_service.search_stocks.assert_awaited_once()
    yahoo_provider.search_companies.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_falls_back_to_tapetide_when_nse_empty(
    settings, tapetide_service, yahoo_provider, master_service
) -> None:
    from app.schemas.company_search import CompanySearchResult

    tapetide_service.search_stocks.return_value = [
        CompanySearchResult(
            symbol="ZZZTIDE",
            exchange="NSE",
            company_name="Zzz Tapetide Only",
            sector=None,
            source=TAPETIDE_MCP_SOURCE,
        )
    ]
    yahoo_provider.search_companies.return_value = []
    service = CompanySearchService(settings, tapetide_service, yahoo_provider, master_service)

    response = await service.search("zzztideonly")

    assert response.source == TAPETIDE_MCP_SOURCE
    assert response.results[0].symbol == "ZZZTIDE"
    yahoo_provider.search_companies.assert_not_called()


@pytest.mark.asyncio
async def test_search_rejects_short_query(settings, tapetide_service, yahoo_provider, master_service) -> None:
    service = CompanySearchService(settings, tapetide_service, yahoo_provider, master_service)

    response = await service.search("i")

    assert response.results == []
    tapetide_service.search_stocks.assert_not_called()
    yahoo_provider.search_companies.assert_not_called()


@pytest.mark.asyncio
async def test_provider_fallback_not_called_when_nse_has_results(
    settings, tapetide_service, yahoo_provider, master_service
) -> None:
    service = CompanySearchService(settings, tapetide_service, yahoo_provider, master_service)

    await service.search("hdfc")

    tapetide_service.search_stocks.assert_not_called()
    yahoo_provider.search_companies.assert_not_called()


@pytest.mark.asyncio
async def test_nse_search_is_fast(settings, master_service) -> None:
    service = CompanySearchService(
        Settings(app_env="test", tapetide_mcp_enabled=False, yfinance_enabled=False),
        tapetide_service=None,
        yahoo_provider=None,
        master_service=master_service,
    )

    with patch("app.services.company_search_service.async_timed_operation") as mock_timer:
        mock_timer.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_timer.return_value.__aexit__ = AsyncMock(return_value=None)
        await service.search("inf")

    # Local master path should not await external providers.
    assert mock_timer.called
