"""Yahoo Finance client using yfinance (runs sync calls in a thread pool)."""

import asyncio
from typing import Any

import yfinance as yf

from app.schemas.financial import MarketData
from app.utils.exceptions import ExternalServiceError, TickerNotFoundError
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _fetch_market_data_sync(ticker: str) -> MarketData:
    """Blocking Yahoo Finance call – executed in a worker thread."""
    stock = yf.Ticker(ticker.upper())
    info = stock.info or {}

    if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
        raise TickerNotFoundError(f"No Yahoo Finance data found for ticker: {ticker}")

    return MarketData(
        current_price=info.get("regularMarketPrice") or info.get("currentPrice"),
        previous_close=info.get("previousClose") or info.get("regularMarketPreviousClose"),
        day_high=info.get("dayHigh") or info.get("regularMarketDayHigh"),
        day_low=info.get("dayLow") or info.get("regularMarketDayLow"),
        fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
        fifty_two_week_low=info.get("fiftyTwoWeekLow"),
        volume=info.get("volume") or info.get("regularMarketVolume"),
        average_volume=info.get("averageVolume") or info.get("averageDailyVolume10Day"),
        currency=info.get("currency"),
    )


def _fetch_quote_summary_sync(ticker: str) -> dict[str, Any]:
    """Supplemental quote data when profile fields are sparse."""
    stock = yf.Ticker(ticker.upper())
    return stock.info or {}


class YahooFinanceClient:
    """Wraps yfinance so the rest of the app stays async."""

    async def get_market_data(self, ticker: str) -> MarketData:
        try:
            return await asyncio.to_thread(_fetch_market_data_sync, ticker)
        except TickerNotFoundError:
            raise
        except Exception as exc:
            logger.error("Yahoo Finance error for %s: %s", ticker, exc)
            raise ExternalServiceError(f"Yahoo Finance request failed for {ticker}") from exc

    async def get_info(self, ticker: str) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(_fetch_quote_summary_sync, ticker)
        except Exception as exc:
            logger.error("Yahoo Finance info error for %s: %s", ticker, exc)
            raise ExternalServiceError(f"Yahoo Finance info failed for {ticker}") from exc
