"""Tests for Tapetide MCP service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.providers.data_sources import TAPETIDE_MCP_SOURCE, YAHOO_SOURCE
from app.schemas.financial import CompanyProfile, HistoricalPricePoint
from app.services.financial_data_service import FinancialDataService
from app.services.tapetide_service import TapetideService
from app.utils.exceptions import TapetideMcpServiceError


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        debug=True,
        tapetide_mcp_enabled=True,
        tapetide_api_token="tpt_rt_test_token",
        yfinance_enabled=True,
    )


def _sample_candles() -> list[HistoricalPricePoint]:
    return [
        HistoricalPricePoint(
            date="2025-01-02",
            open=100.0,
            high=105.0,
            low=99.0,
            close=104.0,
            volume=120000,
        )
    ]


def _sample_profile() -> CompanyProfile:
    return CompanyProfile(
        symbol="INFY.NS",
        company_name="Infosys Limited",
        exchange="NSE",
        sector="Technology",
        currency="INR",
        market_cap=1_000_000.0,
    )


@pytest.mark.asyncio
async def test_tapetide_disabled_status() -> None:
    service = TapetideService(Settings(app_env="test", tapetide_mcp_enabled=False))
    status = await service.get_status()
    assert status.enabled is False
    assert status.connected is False


@pytest.mark.asyncio
async def test_tapetide_quote_normalization(settings: Settings) -> None:
    mock_provider = MagicMock()
    mock_provider.call_tool = AsyncMock(
        return_value={
            "symbol": "INFY",
            "ltp": 1520.5,
            "previous_close": 1500.0,
            "open": 1505.0,
            "high": 1530.0,
            "low": 1498.0,
            "volume": 2500000,
        }
    )

    service = TapetideService(settings=settings, provider=mock_provider)
    quote = await service.get_quote("INFY", allow_yahoo_fallback=False)

    assert quote.last_price == 1520.5
    assert quote.exchange == "NSE"
    assert quote.source == TAPETIDE_MCP_SOURCE
    mock_provider.call_tool.assert_awaited_once_with("get_stock_quote", {"symbol": "INFY"})


@pytest.mark.asyncio
async def test_tapetide_history_normalization(settings: Settings) -> None:
    mock_provider = MagicMock()
    mock_provider.call_tool = AsyncMock(
        return_value=[
            {
                "date": "2025-01-02",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 104.0,
                "volume": 120000,
            }
        ]
    )

    service = TapetideService(settings=settings, provider=mock_provider)
    result = await service.get_history(
        "INFY",
        from_date="2025-01-01",
        to_date="2025-01-10",
        allow_yahoo_fallback=False,
    )

    assert len(result.candles) == 1
    assert result.source == TAPETIDE_MCP_SOURCE


@pytest.mark.asyncio
async def test_tapetide_search_normalization(settings: Settings) -> None:
    mock_provider = MagicMock()
    mock_provider.call_tool = AsyncMock(
        return_value={
            "results": [
                {
                    "symbol": "INFY",
                    "company_name": "Infosys Limited",
                    "exchange": "NSE",
                    "sector": "Information Technology",
                }
            ]
        }
    )

    service = TapetideService(settings=settings, provider=mock_provider)
    results = await service.search_stocks("infosys")

    assert len(results) == 1
    assert results[0].symbol == "INFY"
    assert results[0].source == TAPETIDE_MCP_SOURCE


@pytest.mark.asyncio
async def test_tapetide_yahoo_quote_fallback(settings: Settings) -> None:
    mock_provider = MagicMock()
    mock_provider.call_tool = AsyncMock(side_effect=TapetideMcpServiceError("unavailable"))

    mock_yahoo = MagicMock()
    mock_yahoo.get_current_price = AsyncMock(return_value=1500.0)
    mock_yahoo.get_market_data = AsyncMock(
        return_value=MagicMock(day_high=1510.0, day_low=1490.0, previous_close=1495.0, volume=1000)
    )

    service = TapetideService(settings=settings, provider=mock_provider, yahoo_provider=mock_yahoo)
    quote = await service.get_quote("INFY")

    assert quote.last_price == 1500.0
    assert quote.source == YAHOO_SOURCE
    # Regression: the Yahoo fallback previously left change/change_percent
    # as None even though it has everything needed to compute them.
    assert quote.previous_close == 1495.0
    assert quote.change == pytest.approx(5.0)
    assert quote.change_percent == pytest.approx((5.0 / 1495.0) * 100)


@pytest.mark.asyncio
async def test_financial_data_service_uses_tapetide_before_yahoo(settings: Settings) -> None:
    mock_provider = MagicMock()
    mock_provider.call_tool = AsyncMock(
        return_value={
            "profile": {
                "company_name": "Infosys Limited",
                "sector": "Technology",
                "market_cap": 1_000_000.0,
            }
        }
    )
    mock_provider.health_check = AsyncMock(return_value=True)

    tapetide = TapetideService(settings=settings, provider=mock_provider)
    tapetide.get_live_price = AsyncMock(return_value=(1520.0, TAPETIDE_MCP_SOURCE))

    yahoo = MagicMock()
    yahoo.get_company_profile = AsyncMock(return_value=_sample_profile())
    yahoo.get_financial_ratios = AsyncMock(return_value=[])
    yahoo.get_key_metrics = AsyncMock(return_value=[])
    yahoo.get_market_data = AsyncMock(return_value=MagicMock(current_price=1500.0, currency="INR"))
    yahoo.get_supplemental_metrics = AsyncMock(return_value={})
    yahoo.name = "yahoo"

    financial = FinancialDataService(provider=yahoo, tapetide_service=tapetide)
    summary = await financial.get_summary("INFY")

    assert summary.fundamentals_source == TAPETIDE_MCP_SOURCE
    assert summary.price_source == TAPETIDE_MCP_SOURCE


@pytest.mark.asyncio
async def test_financial_data_history_priority_tapetide_then_kite(settings: Settings) -> None:
    mock_provider = MagicMock()
    mock_provider.call_tool = AsyncMock(
        return_value=[
            {
                "date": "2025-01-02",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 104.0,
                "volume": 120000,
            }
        ]
    )

    tapetide = TapetideService(settings=settings, provider=mock_provider)
    yahoo = MagicMock()
    yahoo.get_historical_candles = AsyncMock(return_value=[])
    yahoo.name = "yahoo"

    financial = FinancialDataService(provider=yahoo, tapetide_service=tapetide)
    result = await financial.get_price_history_with_source("INFY", from_date="2025-01-01", to_date="2025-01-10")

    assert result.source == TAPETIDE_MCP_SOURCE
    assert len(result.candles) == 1
