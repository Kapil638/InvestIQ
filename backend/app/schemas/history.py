"""Historical OHLC candle schemas for chart endpoints."""

from pydantic import BaseModel, Field


class HistoricalCandle(BaseModel):
    """Single OHLCV candle for chart rendering."""

    timestamp: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
