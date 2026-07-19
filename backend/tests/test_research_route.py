from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_financial_data_service
from app.core.config import Settings
from app.main import create_app
from app.schemas.financial import (
    CompanyProfile,
    FinancialResearchResponse,
    MarketData,
)


def _sample_response() -> FinancialResearchResponse:
    return FinancialResearchResponse(
        ticker="INFY.NS",
        collected_at=datetime.now(UTC),
        profile=CompanyProfile(symbol="INFY.NS", company_name="Infosys Limited"),
        market_data=MarketData(current_price=1500.0, currency="INR"),
        data_sources=["yahoo_finance"],
    )


def test_research_endpoint_returns_financial_data() -> None:
    settings = Settings(app_env="test", debug=True, yfinance_enabled=True)
    app = create_app(settings=settings)

    mock_service = AsyncMock()
    mock_service.collect.return_value = _sample_response()
    app.dependency_overrides[get_financial_data_service] = lambda: mock_service

    client = TestClient(app)
    response = client.post(f"{settings.api_prefix}/research/INFY")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "INFY.NS"
    assert data["profile"]["company_name"] == "Infosys Limited"
    assert data["market_data"]["current_price"] == 1500.0
    mock_service.collect.assert_awaited_once_with("INFY")


def test_research_endpoint_returns_503_without_yfinance_enabled() -> None:
    settings = Settings(app_env="test", debug=True, yfinance_enabled=False)
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.post(f"{settings.api_prefix}/research/INFY")

    assert response.status_code == 503
    assert "YFINANCE_ENABLED" in response.json()["detail"]
