from unittest.mock import AsyncMock

import pytest

from app.schemas.financial import (
    BalanceSheet,
    CompanyProfile,
    FinancialRatios,
    IncomeStatement,
    KeyMetrics,
    MarketData,
)
from app.services.financial_data_service import FinancialDataService
from tests.fixtures.financial_data import SAMPLE_YAHOO_INFO


@pytest.fixture
def mock_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.name = "yahoo_finance"

    provider.get_company_profile.return_value = CompanyProfile(
        symbol="INFY.NS",
        company_name="Infosys Limited",
        exchange="NSI",
        sector="Technology",
        industry="Information Technology Services",
        country="India",
        currency="INR",
        market_cap=700000000000,
        price=1500.0,
    )
    provider.get_income_statement.return_value = [
        IncomeStatement(date="2024-03-31", period="FY", revenue=1000000, net_income=250000)
    ]
    provider.get_balance_sheet.return_value = [
        BalanceSheet(date="2024-03-31", period="FY", total_assets=500000, total_equity=300000)
    ]
    provider.get_cash_flow.return_value = []
    provider.get_financial_ratios.return_value = [
        FinancialRatios(
            date="2024-03-31",
            period="TTM",
            debt_to_equity=0.05,
            return_on_equity=0.28,
            net_profit_margin=0.18,
            price_to_earnings=25.5,
            price_to_book=8.2,
        )
    ]
    provider.get_key_metrics.return_value = [
        KeyMetrics(date="2024-03-31", period="TTM", pe_ratio=25.5, pb_ratio=8.2)
    ]
    provider.get_market_data.return_value = MarketData(
        current_price=1500.0,
        previous_close=1490.0,
        currency="INR",
    )
    provider.get_supplemental_metrics.return_value = {
        "revenue_growth": SAMPLE_YAHOO_INFO["revenueGrowth"],
        "dividend_yield": SAMPLE_YAHOO_INFO["dividendYield"],
    }
    return provider


@pytest.fixture
def financial_data_service(mock_provider: AsyncMock) -> FinancialDataService:
    return FinancialDataService(provider=mock_provider)
