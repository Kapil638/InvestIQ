from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_kite_service
from app.core.config import Settings
from app.main import create_app
from app.providers.kite_mcp_provider import KiteMcpProvider, TRADING_TOOL_NAMES
from app.schemas.financial import CompanyProfile, FinancialSummaryResponse, MarketData
from app.schemas.kite import KiteQuoteResponse, KiteStatusResponse
from app.services.kite_service import KiteService, DISABLED_MESSAGE
from app.utils.exceptions import KiteBlockedToolError, KiteNotEnabledError


def test_kite_status_disabled() -> None:
    settings = Settings(app_env="test", debug=True, kite_mcp_enabled=False)
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.get(f"{settings.api_prefix}/kite/status")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["message"] == DISABLED_MESSAGE
    assert "place_order" in data["excluded_tools"]


def test_kite_quote_disabled_returns_503() -> None:
    settings = Settings(app_env="test", debug=True, kite_mcp_enabled=False)
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.get(f"{settings.api_prefix}/kite/quotes/INFY")

    assert response.status_code == 503
    assert DISABLED_MESSAGE in response.json()["detail"]


def test_kite_status_enabled_connected() -> None:
    settings = Settings(app_env="test", debug=True, kite_mcp_enabled=True)
    app = create_app(settings=settings)

    mock_service = AsyncMock()
    mock_service.get_status.return_value = KiteStatusResponse(
        enabled=True,
        read_only=True,
        connected=True,
        message="Kite MCP connected. Market data and portfolio tools available.",
        mcp_url="https://mcp.kite.trade/mcp",
        excluded_tools=["place_order"],
        available_read_tools=["get_quotes", "get_holdings"],
    )
    app.dependency_overrides[get_kite_service] = lambda: mock_service

    client = TestClient(app)
    response = client.get(f"{settings.api_prefix}/kite/status")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["connected"] is True
    assert data["read_only"] is True


def test_blocked_trading_tools() -> None:
    settings = Settings(
        app_env="test",
        debug=True,
        kite_mcp_enabled=True,
        kite_mcp_read_only=True,
    )
    provider = KiteMcpProvider(settings)

    assert provider.is_tool_allowed("get_quotes") is True
    assert provider.is_tool_allowed("get_holdings") is True
    assert provider.is_tool_allowed("place_order") is False

    with pytest.raises(KiteBlockedToolError):
        provider.assert_tool_allowed("place_order")


def test_excluded_tools_from_env() -> None:
    settings = Settings(
        app_env="test",
        debug=True,
        kite_mcp_enabled=True,
        kite_excluded_tools="place_order,cancel_order",
    )
    provider = KiteMcpProvider(settings)

    assert provider.is_tool_allowed("place_order") is False
    assert provider.is_tool_allowed("cancel_order") is False


def test_trading_tool_names_include_order_endpoints() -> None:
    for tool in (
        "place_order",
        "modify_order",
        "cancel_order",
        "place_gtt_order",
        "modify_gtt_order",
        "delete_gtt_order",
    ):
        assert tool in TRADING_TOOL_NAMES


@pytest.mark.asyncio
async def test_quote_fallback_to_yahoo() -> None:
    settings = Settings(app_env="test", debug=True, kite_mcp_enabled=True, yfinance_enabled=True)
    mock_provider = MagicMock()
    mock_provider.enabled = True
    mock_provider.read_only = True
    mock_provider.call_tool = AsyncMock(side_effect=RuntimeError("kite down"))

    mock_yahoo = MagicMock()
    mock_yahoo.get_current_price = AsyncMock(return_value=1525.5)
    mock_yahoo.get_market_data = AsyncMock(
        return_value=MarketData(
            current_price=1525.5,
            previous_close=1500.0,
            day_high=1530.0,
            day_low=1495.0,
            volume=1000000,
            currency="INR",
        )
    )

    service = KiteService(settings=settings, provider=mock_provider, yahoo_provider=mock_yahoo)
    quote = await service.get_quote("INFY")

    assert quote.source == "Yahoo Finance"
    assert quote.last_price == 1525.5
    mock_yahoo.get_current_price.assert_awaited()


@pytest.mark.asyncio
async def test_get_live_price_falls_back_to_yahoo_when_kite_disabled() -> None:
    settings = Settings(app_env="test", debug=True, kite_mcp_enabled=False, yfinance_enabled=True)
    mock_yahoo = MagicMock()
    mock_yahoo.get_current_price = AsyncMock(return_value=1400.0)

    service = KiteService(settings=settings, yahoo_provider=mock_yahoo)
    price, source = await service.get_live_price("INFY")

    assert price == 1400.0
    assert source == "Yahoo Finance"


@pytest.mark.asyncio
async def test_financial_summary_uses_kite_price_when_available() -> None:
    from app.services.financial_data_service import FinancialDataService

    settings = Settings(app_env="test", debug=True, yfinance_enabled=True, kite_mcp_enabled=True)
    mock_provider = MagicMock()
    mock_provider.get_company_profile = AsyncMock(
        return_value=CompanyProfile(symbol="INFY.NS", company_name="Infosys Limited", price=1500.0)
    )
    mock_provider.get_financial_ratios = AsyncMock(return_value=[])
    mock_provider.get_key_metrics = AsyncMock(return_value=[])
    mock_provider.get_market_data = AsyncMock(return_value=MarketData(current_price=1500.0, currency="INR"))
    mock_provider.get_supplemental_metrics = AsyncMock(return_value={})
    mock_provider.name = "Yahoo Finance"

    mock_kite = MagicMock()
    mock_kite.get_live_price = AsyncMock(return_value=(1550.0, "Kite Connect"))

    service = FinancialDataService(provider=mock_provider, kite_service=mock_kite)
    summary = await service.get_summary("INFY")

    assert summary.current_price == 1550.0
    assert summary.price_source == "kite"
    assert summary.data_source == "yahoo"


def test_kite_service_assert_enabled_raises() -> None:
    settings = Settings(app_env="test", debug=True, kite_mcp_enabled=False)
    service = KiteService(settings=settings)

    with pytest.raises(KiteNotEnabledError, match=DISABLED_MESSAGE):
        service.assert_enabled()
