from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_portfolio_analyze_service, get_portfolio_holdings_service
from app.core.config import Settings
from app.main import create_app
from app.providers.kite_mcp_provider import KiteMcpProvider, TRADING_TOOL_NAMES
from app.schemas.kite import KiteHoldingItem, KiteHoldingsResponse, KiteStatusResponse
from app.schemas.portfolio import PortfolioAnalyzeResponse, PortfolioHoldingsResponse
from app.services.portfolio_analyze_service import PortfolioAnalyzeService, _parse_response
from app.services.portfolio_holdings_service import (
    AUTH_REQUIRED_MESSAGE,
    PortfolioHoldingsService,
    _normalize_holding,
)
from app.services.symbol_resolver_service import get_symbol_resolver_service


def _holding_item() -> KiteHoldingItem:
    return KiteHoldingItem(
        tradingsymbol="INFY",
        exchange="NSE",
        quantity=10.0,
        average_price=1500.0,
        last_price=1600.0,
        pnl=1000.0,
        company_name="Infosys Ltd",
        sector="Technology",
        day_change=1.2,
    )


def test_holdings_normalization_computes_values() -> None:
    resolver = get_symbol_resolver_service()
    resolver.ensure_loaded()
    holding = _normalize_holding(_holding_item(), resolver)

    assert holding.symbol == "INFY"
    assert holding.company_name == "Infosys Limited"
    assert holding.invested_value == 15000.0
    assert holding.current_value == 16000.0
    assert holding.pnl == 1000.0
    assert holding.pnl_percent == pytest.approx(6.666, rel=0.01)
    assert holding.price_source == "kite"
    assert holding.sector == "Technology"


@pytest.mark.asyncio
async def test_holdings_auth_required_when_not_connected() -> None:
    mock_kite = MagicMock()
    mock_kite.enabled = True
    mock_kite.get_status = AsyncMock(
        return_value=KiteStatusResponse(
            enabled=True,
            read_only=True,
            authenticated=False,
            connected=False,
            message="Kite is enabled but Zerodha authentication is required.",
        )
    )

    service = PortfolioHoldingsService(mock_kite)
    result = await service.get_holdings()

    assert result.auth_required is True
    assert result.message == AUTH_REQUIRED_MESSAGE
    assert result.holdings == []


@pytest.mark.asyncio
async def test_holdings_merges_kite_and_groww() -> None:
    from app.schemas.groww import GrowwHoldingItem, GrowwHoldingsResponse

    mock_kite = MagicMock()
    mock_kite.enabled = True
    mock_kite.get_status = AsyncMock(
        return_value=KiteStatusResponse(
            enabled=True, read_only=True, authenticated=True, connected=True, message="connected"
        )
    )
    mock_kite.get_holdings = AsyncMock(
        return_value=KiteHoldingsResponse(holdings=[_holding_item()], source="Kite Connect")
    )

    mock_groww = MagicMock()
    mock_groww.enabled = True
    mock_groww.get_holdings = AsyncMock(
        return_value=GrowwHoldingsResponse(
            holdings=[
                GrowwHoldingItem(
                    trading_symbol="COALINDIA",
                    exchange="NSE",
                    quantity=100.0,
                    average_price=400.0,
                    last_price=450.0,
                    pnl=5000.0,
                )
            ],
            source="Groww",
        )
    )

    service = PortfolioHoldingsService(mock_kite, groww_service=mock_groww)
    result = await service.get_holdings()

    assert result.auth_required is False
    assert len(result.holdings) == 2
    sources = {h.price_source for h in result.holdings}
    assert sources == {"kite", "groww"}


@pytest.mark.asyncio
async def test_holdings_groww_failure_does_not_blank_kite() -> None:
    mock_kite = MagicMock()
    mock_kite.enabled = True
    mock_kite.get_status = AsyncMock(
        return_value=KiteStatusResponse(
            enabled=True, read_only=True, authenticated=True, connected=True, message="connected"
        )
    )
    mock_kite.get_holdings = AsyncMock(
        return_value=KiteHoldingsResponse(holdings=[_holding_item()], source="Kite Connect")
    )

    mock_groww = MagicMock()
    mock_groww.enabled = True
    mock_groww.get_holdings = AsyncMock(side_effect=RuntimeError("Groww unreachable"))

    service = PortfolioHoldingsService(mock_kite, groww_service=mock_groww)
    result = await service.get_holdings()

    assert len(result.holdings) == 1
    assert result.holdings[0].price_source == "kite"


@pytest.mark.asyncio
async def test_holdings_returns_normalized_rows_when_connected() -> None:
    mock_kite = MagicMock()
    mock_kite.enabled = True
    mock_kite.get_status = AsyncMock(
        return_value=KiteStatusResponse(
            enabled=True,
            read_only=True,
            authenticated=True,
            connected=True,
            message="connected",
        )
    )
    mock_kite.get_holdings = AsyncMock(
        return_value=KiteHoldingsResponse(
            holdings=[_holding_item()],
            source="Kite Connect",
        )
    )

    service = PortfolioHoldingsService(mock_kite)
    result = await service.get_holdings()

    assert result.auth_required is False
    assert len(result.holdings) == 1
    assert result.holdings[0].symbol == "INFY"
    assert result.holdings[0].current_value == 16000.0


def test_holdings_endpoint_auth_required() -> None:
    settings = Settings(app_env="test", debug=True, kite_mcp_enabled=True)
    app = create_app(settings=settings)

    mock_service = AsyncMock()
    mock_service.get_holdings.return_value = PortfolioHoldingsResponse(
        holdings=[],
        auth_required=True,
        message=AUTH_REQUIRED_MESSAGE,
        source="Kite Connect",
    )
    app.dependency_overrides[get_portfolio_holdings_service] = lambda: mock_service

    client = TestClient(app)
    response = client.get(f"{settings.api_prefix}/kite/holdings")

    assert response.status_code == 200
    data = response.json()
    assert data["auth_required"] is True
    assert "authentication" in data["message"].lower()


def test_portfolio_analyze_endpoint() -> None:
    settings = Settings(app_env="test", debug=True, openrouter_api_key="test-key")
    app = create_app(settings=settings)

    mock_service = AsyncMock()
    mock_service.analyze.return_value = PortfolioAnalyzeResponse(
        summary="Balanced IT-heavy portfolio.",
        concentration_risk="Top holding exceeds 25% allocation.",
        strong_holdings=["INFY"],
        weak_holdings=["XYZ"],
        rebalance_suggestions=["Research suggestion: review sector concentration."],
        three_year_view="Suitable for long-term research monitoring.",
        watchlist_actions=["Monitor INFY earnings"],
    )
    app.dependency_overrides[get_portfolio_analyze_service] = lambda: mock_service

    client = TestClient(app)
    response = client.post(
        f"{settings.api_prefix}/portfolio/analyze",
        json={
            "holdings": [
                {
                    "symbol": "INFY",
                    "quantity": 10,
                    "current_value": 16000,
                    "sector": "Technology",
                }
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "Balanced" in data["summary"]
    assert data["strong_holdings"] == ["INFY"]
    mock_service.analyze.assert_awaited_once()


def test_portfolio_analyze_service_parses_json() -> None:
    raw = """{
      "summary": "Portfolio summary",
      "concentration_risk": "Moderate",
      "strong_holdings": ["TCS"],
      "weak_holdings": [],
      "sector_exposure": [{"sector": "IT", "allocation_percent": 40, "holdings": ["TCS"]}],
      "rebalance_suggestions": ["Research suggestion: diversify"],
      "three_year_view": "Hold quality names",
      "watchlist_actions": ["Review TCS"]
    }"""

    result = _parse_response(raw)

    assert result.summary == "Portfolio summary"
    assert result.sector_exposure[0].sector == "IT"


def test_trading_tools_remain_blocked() -> None:
    settings = Settings(app_env="test", debug=True, kite_mcp_enabled=True, kite_mcp_read_only=True)
    provider = KiteMcpProvider(settings)

    for tool in TRADING_TOOL_NAMES:
        assert provider.is_tool_allowed(tool) is False

    assert provider.is_tool_allowed("get_holdings") is True
    assert provider.is_tool_allowed("get_quotes") is True


def test_kite_status_live_vs_auth_vs_disabled() -> None:
    settings = Settings(app_env="test", debug=True, kite_mcp_enabled=False)
    app = create_app(settings=settings)
    client = TestClient(app)

    disabled = client.get(f"{settings.api_prefix}/kite/status").json()
    assert disabled["enabled"] is False

    settings_enabled = Settings(app_env="test", debug=True, kite_mcp_enabled=True)
    app2 = create_app(settings=settings_enabled)

    mock_kite = AsyncMock()
    mock_kite.get_status.return_value = KiteStatusResponse(
        enabled=True,
        read_only=True,
        authenticated=False,
        connected=False,
        message="auth needed",
    )
    from app.api.dependencies import get_kite_service

    app2.dependency_overrides[get_kite_service] = lambda: mock_kite
    client2 = TestClient(app2)
    auth = client2.get(f"{settings_enabled.api_prefix}/kite/status").json()
    assert auth["enabled"] is True
    assert auth["connected"] is False

    mock_kite.get_status.return_value = KiteStatusResponse(
        enabled=True,
        read_only=True,
        authenticated=True,
        connected=True,
        user_id="AB1234",
        broker="Zerodha",
        message="connected",
    )
    live = client2.get(f"{settings_enabled.api_prefix}/kite/status").json()
    assert live["connected"] is True
