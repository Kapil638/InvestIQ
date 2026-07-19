"""Pydantic models for Kite MCP market data and portfolio endpoints."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.schemas.financial import HistoricalPricePoint


class KiteStatusResponse(BaseModel):
    enabled: bool
    read_only: bool
    authenticated: bool = False
    connected: bool = False
    user_id: str | None = None
    broker: str | None = None
    message: str
    mcp_url: str | None = None
    excluded_tools: list[str] = Field(default_factory=list)
    available_read_tools: list[str] = Field(default_factory=list)


class KiteQuoteResponse(BaseModel):
    symbol: str
    kite_symbol: str
    exchange: str | None = None
    last_price: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    change: float | None = None
    change_percent: float | None = None
    currency: str = "INR"
    source: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class KiteHistoryResponse(BaseModel):
    symbol: str
    kite_symbol: str
    interval: str = "day"
    candles: list[HistoricalPricePoint] = Field(default_factory=list)
    source: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class KiteHoldingItem(BaseModel):
    tradingsymbol: str
    exchange: str | None = None
    quantity: float | None = None
    average_price: float | None = None
    last_price: float | None = None
    pnl: float | None = None
    product: str | None = None
    company_name: str | None = None
    sector: str | None = None
    day_change: float | None = None


class KiteHoldingsResponse(BaseModel):
    holdings: list[KiteHoldingItem] = Field(default_factory=list)
    source: str = "Kite Connect"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class KitePositionItem(BaseModel):
    tradingsymbol: str
    exchange: str | None = None
    quantity: float | None = None
    average_price: float | None = None
    last_price: float | None = None
    pnl: float | None = None
    product: str | None = None


class KitePositionsResponse(BaseModel):
    net: list[KitePositionItem] = Field(default_factory=list)
    day: list[KitePositionItem] = Field(default_factory=list)
    source: str = "Kite Connect"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
