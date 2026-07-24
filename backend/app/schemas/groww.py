"""Pydantic models for the Groww Trade API (read-only: holdings, positions, margin)."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class GrowwStatusResponse(BaseModel):
    enabled: bool
    read_only: bool = True
    credentials_configured: bool = False
    connected: bool = False
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GrowwHoldingItem(BaseModel):
    trading_symbol: str
    isin: str | None = None
    exchange: str | None = None
    quantity: float | None = None
    average_price: float | None = None
    last_price: float | None = None
    pnl: float | None = None


class GrowwHoldingsResponse(BaseModel):
    holdings: list[GrowwHoldingItem] = Field(default_factory=list)
    source: str = "Groww"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GrowwPositionItem(BaseModel):
    trading_symbol: str
    segment: str | None = None
    quantity: float | None = None
    net_price: float | None = None
    realised_pnl: float | None = None
    product: str | None = None


class GrowwPositionsResponse(BaseModel):
    positions: list[GrowwPositionItem] = Field(default_factory=list)
    source: str = "Groww"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
