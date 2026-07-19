"""Portfolio holdings and AI analysis schemas."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class PortfolioHolding(BaseModel):
    symbol: str
    exchange: str | None = None
    company_name: str | None = None
    quantity: float | None = None
    average_price: float | None = None
    last_price: float | None = None
    invested_value: float | None = None
    current_value: float | None = None
    pnl: float | None = None
    pnl_percent: float | None = None
    day_change: float | None = None
    sector: str | None = None
    price_source: str = "kite"


class PortfolioHoldingsResponse(BaseModel):
    holdings: list[PortfolioHolding] = Field(default_factory=list)
    auth_required: bool = False
    message: str | None = None
    source: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PortfolioAnalyzeHoldingInput(BaseModel):
    symbol: str
    exchange: str | None = None
    company_name: str | None = None
    quantity: float | None = None
    average_price: float | None = None
    last_price: float | None = None
    invested_value: float | None = None
    current_value: float | None = None
    pnl: float | None = None
    pnl_percent: float | None = None
    sector: str | None = None


class PortfolioAnalyzeRequest(BaseModel):
    holdings: list[PortfolioAnalyzeHoldingInput] = Field(min_length=1)


class SectorExposureItem(BaseModel):
    sector: str
    allocation_percent: float
    holdings: list[str] = Field(default_factory=list)


class PortfolioAnalyzeResponse(BaseModel):
    summary: str
    concentration_risk: str
    strong_holdings: list[str] = Field(default_factory=list)
    weak_holdings: list[str] = Field(default_factory=list)
    sector_exposure: list[SectorExposureItem] = Field(default_factory=list)
    rebalance_suggestions: list[str] = Field(default_factory=list)
    three_year_view: str
    watchlist_actions: list[str] = Field(default_factory=list)
