"""Tests for Tapetide MCP routes."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_financial_data_service, get_tapetide_service
from app.main import create_app
from app.providers.data_sources import TAPETIDE_MCP_SOURCE
from app.schemas.tapetide import TapetideQuoteResponse, TapetideStatusResponse
from app.services.financial_data_service import PriceHistoryResult


def test_tapetide_status_route() -> None:
    mock_service = AsyncMock()
    mock_service.get_status.return_value = TapetideStatusResponse(
        enabled=True,
        read_only=True,
        connected=True,
        message="Connected to Tapetide NSE/BSE MCP.",
        token_configured=True,
    )

    app = create_app()
    app.dependency_overrides[get_tapetide_service] = lambda: mock_service
    client = TestClient(app)

    response = client.get("/api/v1/tapetide/status")
    assert response.status_code == 200
    assert response.json()["connected"] is True


def test_tapetide_quote_route() -> None:
    mock_service = AsyncMock()
    mock_service.get_quote.return_value = TapetideQuoteResponse(
        symbol="INFY.NS",
        exchange="NSE",
        last_price=1520.0,
        source=TAPETIDE_MCP_SOURCE,
    )

    app = create_app()
    app.dependency_overrides[get_tapetide_service] = lambda: mock_service
    client = TestClient(app)

    response = client.get("/api/v1/tapetide/quotes/INFY")
    assert response.status_code == 200
    assert response.json()["source"] == TAPETIDE_MCP_SOURCE


def test_market_history_route_source_field() -> None:
    mock_financial = AsyncMock()
    mock_financial.get_price_history_with_source.return_value = PriceHistoryResult(
        candles=[],
        source=TAPETIDE_MCP_SOURCE,
    )

    app = create_app()
    app.dependency_overrides[get_financial_data_service] = lambda: mock_financial
    client = TestClient(app)

    response = client.get("/api/v1/market/history/INFY")
    assert response.status_code == 200
    assert response.json()["source"] == TAPETIDE_MCP_SOURCE
