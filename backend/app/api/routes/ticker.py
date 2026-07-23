"""Public market ticker for the pre-login page - deliberately NOT behind the
owner-auth gate (it renders before the user has a session). Registered
unguarded in main.py, same as health.router.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends

from app.api.dependencies import get_tapetide_service
from app.schemas.ticker import TickerItem, TickerResponse
from app.services.tapetide_service import TapetideService
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["ticker"])

_IST = ZoneInfo("Asia/Kolkata")

# Top 10 NIFTY 50 constituents by index weight - a fixed, manually-curated
# list (not pulled from a live index-constituent feed), since weights only
# drift slowly. Revisit if it falls too far out of date.
TOP_NIFTY_SYMBOLS: list[tuple[str, str]] = [
    ("RELIANCE", "Reliance Industries"),
    ("HDFCBANK", "HDFC Bank"),
    ("ICICIBANK", "ICICI Bank"),
    ("INFY", "Infosys"),
    ("TCS", "TCS"),
    ("BHARTIARTL", "Bharti Airtel"),
    ("ITC", "ITC"),
    ("LT", "Larsen & Toubro"),
    ("SBIN", "State Bank of India"),
    ("HINDUNILVR", "Hindustan Unilever"),
]

_MAX_CONCURRENT_QUOTES = 5

# Independent, always-on cache for this endpoint specifically - it's public
# and unauthenticated (unlike every other route in this app), so it needs its
# own abuse-resistant TTL regardless of the global CACHE_ENABLED setting.
# Deliberately long: Tapetide's free tier has a shared DAILY quota across the
# entire app (fundamentals, portfolio, etc. all draw from the same budget) -
# a decorative login-page ticker refreshing every 30s exhausted it in minutes
# during testing. This is illustrative flavor, not a trading terminal; 15
# minutes of staleness costs nothing real and protects the shared quota.
_CACHE_TTL_SECONDS = 900.0
_cache: tuple[float, TickerResponse] | None = None
_cache_lock = asyncio.Lock()


def _is_nse_market_open(now: datetime) -> bool:
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return open_time <= now <= close_time


async def _fetch_quote(
    tapetide: TapetideService, semaphore: asyncio.Semaphore, symbol: str, name: str
) -> TickerItem | None:
    async with semaphore:
        try:
            quote = await tapetide.get_quote(symbol)
        except Exception as exc:  # noqa: BLE001 — one bad symbol must not sink the whole banner
            logger.warning("Ticker quote unavailable for %s: %s", symbol, exc)
            return None
        if quote.last_price is None:
            return None
        return TickerItem(
            symbol=symbol,
            name=name,
            price=quote.last_price,
            change_percent=quote.change_percent,
        )


async def _build_ticker_response(tapetide: TapetideService) -> TickerResponse:
    now = datetime.now(_IST)
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_QUOTES)
    results = await asyncio.gather(
        *(_fetch_quote(tapetide, semaphore, symbol, name) for symbol, name in TOP_NIFTY_SYMBOLS)
    )
    items = [item for item in results if item is not None]
    return TickerResponse(
        market_open=_is_nse_market_open(now),
        as_of=now.isoformat(),
        items=items,
    )


@router.get("/ticker/nifty-top10", response_model=TickerResponse)
async def nifty_top_10_ticker(
    tapetide: TapetideService = Depends(get_tapetide_service),
) -> TickerResponse:
    """Top 10 NIFTY stocks by index weight, for the login page's ticker banner."""
    global _cache

    now_monotonic = time.monotonic()
    async with _cache_lock:
        if _cache is not None and now_monotonic - _cache[0] < _CACHE_TTL_SECONDS:
            return _cache[1]

        response = await _build_ticker_response(tapetide)
        _cache = (now_monotonic, response)
        return response
