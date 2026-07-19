from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_financial_data_service
from app.core.config import Settings
from app.main import create_app
from app.schemas.financial import FinancialSummaryResponse


def _sample_summary() -> FinancialSummaryResponse:
    return FinancialSummaryResponse(
        ticker="INFY.NS",
        company_name="Infosys Limited",
        sector="Technology",
        industry="Information Technology Services",
        market_cap=700000000000,
        current_price=1500.0,
        currency="INR",
        pe_ratio=25.5,
        pb_ratio=8.2,
        roe=0.28,
        debt_to_equity=0.05,
        revenue_growth=0.12,
        profit_margin=0.18,
        dividend_yield=0.02,
        data_source="Yahoo Finance",
        data_timestamp=datetime.now(UTC),
    )


def test_financials_endpoint_returns_summary() -> None:
    settings = Settings(app_env="test", debug=True, yfinance_enabled=True)
    app = create_app(settings=settings)

    mock_service = AsyncMock()
    mock_service.get_summary.return_value = _sample_summary()
    app.dependency_overrides[get_financial_data_service] = lambda: mock_service

    client = TestClient(app)
    response = client.get(f"{settings.api_prefix}/financials/INFY")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "INFY.NS"
    assert data["company_name"] == "Infosys Limited"
    assert data["currency"] == "INR"
    assert data["data_source"] == "Yahoo Finance"
    mock_service.get_summary.assert_awaited_once_with("INFY")


def test_financials_endpoint_returns_503_when_yfinance_disabled() -> None:
    settings = Settings(app_env="test", debug=True, yfinance_enabled=False)
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.get(f"{settings.api_prefix}/financials/INFY")

    assert response.status_code == 503
    assert "YFINANCE_ENABLED" in response.json()["detail"]
