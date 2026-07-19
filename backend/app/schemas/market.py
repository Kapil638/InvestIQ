"""Provider-agnostic market history response."""

from pydantic import BaseModel, Field

from app.schemas.history import HistoricalCandle


class MarketHistoryResponse(BaseModel):
    symbol: str
    interval: str = "day"
    candles: list[HistoricalCandle] = Field(default_factory=list)
    source: str = "yahoo"
