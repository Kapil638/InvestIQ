"""Pydantic models for structured financial data (Agent 1 output)."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    symbol: str
    company_name: str
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    currency: str | None = None
    market_cap: float | None = None
    price: float | None = None
    beta: float | None = None
    description: str | None = None
    ceo: str | None = None
    website: str | None = None
    ipo_date: str | None = None


class IncomeStatement(BaseModel):
    date: str
    period: str | None = None
    revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    eps: float | None = None
    ebitda: float | None = None


class BalanceSheet(BaseModel):
    date: str
    period: str | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    total_equity: float | None = None
    total_debt: float | None = None
    cash_and_equivalents: float | None = None


class CashFlowStatement(BaseModel):
    date: str
    period: str | None = None
    operating_cash_flow: float | None = None
    investing_cash_flow: float | None = None
    financing_cash_flow: float | None = None
    free_cash_flow: float | None = None
    capital_expenditure: float | None = None


class FinancialRatios(BaseModel):
    date: str
    period: str | None = None
    current_ratio: float | None = None
    debt_to_equity: float | None = None
    return_on_equity: float | None = None
    return_on_assets: float | None = None
    gross_profit_margin: float | None = None
    net_profit_margin: float | None = None
    price_to_earnings: float | None = None
    price_to_book: float | None = None


class KeyMetrics(BaseModel):
    date: str
    period: str | None = None
    revenue_per_share: float | None = None
    net_income_per_share: float | None = None
    enterprise_value: float | None = None
    ev_to_ebitda: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None


class MarketData(BaseModel):
    current_price: float | None = None
    previous_close: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    volume: int | None = None
    average_volume: int | None = None
    currency: str | None = None


class HistoricalPricePoint(BaseModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None


class FinancialSummaryResponse(BaseModel):
    """Compact financial snapshot for Indian equities (MVP test endpoint)."""

    ticker: str
    company_name: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: float | None = None
    current_price: float | None = None
    currency: str = "INR"
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    revenue_growth: float | None = None
    profit_margin: float | None = None
    dividend_yield: float | None = None
    data_source: str = "yahoo"
    price_source: str = "yahoo"
    fundamentals_source: str = "yahoo"
    data_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DataCollectionWarning(BaseModel):
    source: str
    message: str


class FinancialResearchResponse(BaseModel):
    """Structured output from Agent 1 – facts only, no opinions."""

    ticker: str
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    profile: CompanyProfile
    income_statements: list[IncomeStatement] = Field(default_factory=list)
    balance_sheets: list[BalanceSheet] = Field(default_factory=list)
    cash_flow_statements: list[CashFlowStatement] = Field(default_factory=list)
    ratios: list[FinancialRatios] = Field(default_factory=list)
    key_metrics: list[KeyMetrics] = Field(default_factory=list)
    market_data: MarketData | None = None
    data_sources: list[str] = Field(default_factory=list)
    warnings: list[DataCollectionWarning] = Field(default_factory=list)
