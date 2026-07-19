"""Abstract financial data provider interface."""

from typing import Protocol

from app.schemas.financial import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    FinancialRatios,
    HistoricalPricePoint,
    IncomeStatement,
    KeyMetrics,
    MarketData,
)


class FinancialDataProvider(Protocol):
    """Provider contract – agents never call yfinance or FMP directly."""

    name: str

    async def get_company_profile(self, ticker: str) -> CompanyProfile: ...

    async def get_current_price(self, ticker: str) -> float | None: ...

    async def get_income_statement(self, ticker: str) -> list[IncomeStatement]: ...

    async def get_balance_sheet(self, ticker: str) -> list[BalanceSheet]: ...

    async def get_cash_flow(self, ticker: str) -> list[CashFlowStatement]: ...

    async def get_financial_ratios(self, ticker: str) -> list[FinancialRatios]: ...

    async def get_key_metrics(self, ticker: str) -> list[KeyMetrics]: ...

    async def get_market_data(self, ticker: str) -> MarketData: ...

    async def get_historical_prices(
        self, ticker: str, period: str = "5y"
    ) -> list[HistoricalPricePoint]: ...
