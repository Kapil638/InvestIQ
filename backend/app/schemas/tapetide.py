"""Pydantic models for Tapetide MCP market data endpoints."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.schemas.company_search import CompanySearchResponse
from app.schemas.financial import HistoricalPricePoint


class TapetideStatusResponse(BaseModel):
    enabled: bool
    read_only: bool
    connected: bool = False
    message: str
    mcp_url: str | None = None
    token_configured: bool = False
    available_read_tools: list[str] = Field(default_factory=list)


class TapetideQuoteResponse(BaseModel):
    symbol: str
    exchange: str | None = None
    last_price: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    previous_close: float | None = None
    volume: int | None = None
    change: float | None = None
    change_percent: float | None = None
    currency: str = "INR"
    source: str = "tapetide_mcp"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TapetideHistoryResponse(BaseModel):
    symbol: str
    exchange: str | None = None
    interval: str = "day"
    candles: list[HistoricalPricePoint] = Field(default_factory=list)
    source: str = "tapetide_mcp"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TapetideSearchResponse(CompanySearchResponse):
    """Alias for company search via Tapetide debug endpoint."""
