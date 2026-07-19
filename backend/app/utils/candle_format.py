"""Convert internal price points to API candle responses."""

from app.schemas.financial import HistoricalPricePoint
from app.schemas.history import HistoricalCandle


def to_historical_candle(point: HistoricalPricePoint) -> HistoricalCandle:
    return HistoricalCandle(
        timestamp=point.date,
        open=point.open,
        high=point.high,
        low=point.low,
        close=point.close,
        volume=point.volume,
    )


def to_historical_candles(points: list[HistoricalPricePoint]) -> list[HistoricalCandle]:
    return [to_historical_candle(p) for p in points]
