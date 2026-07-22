"""Tapetide MCP service – read-only Indian exchange data with Yahoo fallback."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import Settings
from app.providers.data_sources import TAPETIDE_MCP_SOURCE, YAHOO_SOURCE
from app.providers.nse_bse_symbols import resolve_exchange_symbol
from app.providers.tapetide_mcp_provider import TapetideMcpProvider
from app.providers.ticker import normalize_indian_ticker
from app.providers.yahoo_finance_provider import YahooFinanceProvider
from app.schemas.company_search import CompanySearchResult
from app.schemas.financial import CompanyProfile, HistoricalPricePoint, MarketData
from app.schemas.tapetide import TapetideHistoryResponse, TapetideQuoteResponse, TapetideStatusResponse
from app.utils.exceptions import TapetideMcpNotEnabledError, TapetideMcpServiceError
from app.utils.history_timeframe import filter_candles_by_date, yahoo_interval_for
from app.utils.logging import get_logger
from app.utils import ttl_cache
from app.utils.timing import async_timed_operation

logger = get_logger(__name__)

DISABLED_MESSAGE = "Tapetide NSE/BSE MCP is not enabled."
UNAVAILABLE_MESSAGE = "Tapetide NSE/BSE MCP server is not reachable."
TOKEN_MISSING_MESSAGE = "Tapetide API token is not configured."


class TapetideService:
    """Business layer for Tapetide MCP with Yahoo fallback."""

    def __init__(
        self,
        settings: Settings,
        provider: TapetideMcpProvider | None = None,
        yahoo_provider: YahooFinanceProvider | None = None,
    ) -> None:
        self._settings = settings
        self._provider = provider or TapetideMcpProvider(settings)
        self._yahoo = yahoo_provider

    @property
    def enabled(self) -> bool:
        return self._settings.tapetide_mcp_enabled

    @property
    def read_only(self) -> bool:
        return self._settings.tapetide_mcp_read_only

    def assert_enabled(self) -> None:
        if not self.enabled:
            raise TapetideMcpNotEnabledError(DISABLED_MESSAGE)

    async def get_status(self) -> TapetideStatusResponse:
        cached = ttl_cache.get("status", "tapetide")
        if cached is not None:
            return cached

        async with async_timed_operation("tapetide.get_status"):
            response = await self._get_status_uncached()
        ttl_cache.set("status", "tapetide", response)
        return response

    async def _get_status_uncached(self) -> TapetideStatusResponse:
        token_configured = self._settings.tapetide_token_configured
        if not self.enabled:
            return TapetideStatusResponse(
                enabled=False,
                read_only=self.read_only,
                connected=False,
                message=DISABLED_MESSAGE,
                token_configured=token_configured,
            )

        if not token_configured:
            return TapetideStatusResponse(
                enabled=True,
                read_only=self.read_only,
                connected=False,
                message=TOKEN_MISSING_MESSAGE,
                mcp_url=self._settings.tapetide_mcp_url,
                token_configured=False,
            )

        connected = await self._provider.health_check()
        discovered: list[dict[str, Any]] = []
        if connected:
            try:
                discovered = await self._provider.list_tools()
            except TapetideMcpServiceError as exc:
                logger.debug("Tapetide MCP tools probe: %s", exc)
                connected = False

        return TapetideStatusResponse(
            enabled=True,
            read_only=self.read_only,
            connected=connected,
            message="Connected to Tapetide NSE/BSE MCP." if connected else UNAVAILABLE_MESSAGE,
            mcp_url=self._settings.tapetide_mcp_url,
            token_configured=True,
            available_read_tools=self._provider.available_read_tools(discovered),
        )

    async def search_stocks(self, query: str, *, limit: int = 12) -> list[CompanySearchResult]:
        if not self.enabled:
            return []

        try:
            raw = await self._provider.call_tool(
                "search_stocks",
                {"query": query, "limit": limit},
            )
        except TapetideMcpServiceError as exc:
            logger.warning("Tapetide stock search failed: %s", exc)
            raise

        return _parse_search_results(raw, limit=limit)

    async def get_quote(
        self,
        symbol: str,
        *,
        allow_yahoo_fallback: bool = True,
    ) -> TapetideQuoteResponse:
        self.assert_enabled()
        bare, exchange = resolve_exchange_symbol(symbol)

        try:
            raw = await self._provider.call_tool("get_stock_quote", {"symbol": bare})
            parsed = _parse_quote_payload(raw, bare, exchange)
            if parsed.last_price is not None:
                return parsed
        except TapetideMcpServiceError as exc:
            logger.warning("Tapetide quote failed for %s: %s", bare, exc)
            if not allow_yahoo_fallback:
                raise

        if allow_yahoo_fallback and self._yahoo is not None:
            return await self._yahoo_quote_fallback(symbol, bare, exchange)

        raise TapetideMcpServiceError(f"Quote unavailable for {symbol}")

    async def get_history(
        self,
        symbol: str,
        *,
        interval: str = "day",
        from_date: str | None = None,
        to_date: str | None = None,
        allow_yahoo_fallback: bool = True,
    ) -> TapetideHistoryResponse:
        bare, exchange = resolve_exchange_symbol(symbol)
        from_date, to_date = _default_history_range(from_date, to_date)

        if self.enabled:
            try:
                raw = await self._provider.call_tool(
                    "get_price_history",
                    {
                        "symbol": bare,
                        "from_date": from_date,
                        "to_date": to_date,
                        "interval": _tapetide_interval(interval),
                    },
                )
                candles = _parse_history_candles(raw)
                candles = filter_candles_by_date(candles, from_date=from_date, to_date=to_date)
                if candles:
                    return TapetideHistoryResponse(
                        symbol=normalize_indian_ticker(symbol),
                        exchange=exchange,
                        interval=interval,
                        candles=candles,
                        source=TAPETIDE_MCP_SOURCE,
                    )
            except TapetideMcpServiceError as exc:
                logger.warning("Tapetide history failed for %s: %s", bare, exc)
                if not allow_yahoo_fallback:
                    raise

        if allow_yahoo_fallback and self._yahoo is not None:
            return await self._yahoo_history_fallback(
                symbol,
                bare=bare,
                exchange=exchange,
                interval=interval,
                from_date=from_date,
                to_date=to_date,
            )

        return TapetideHistoryResponse(
            symbol=normalize_indian_ticker(symbol),
            exchange=exchange,
            interval=interval,
            candles=[],
            source=TAPETIDE_MCP_SOURCE if self.enabled else YAHOO_SOURCE,
        )

    async def get_company_profile(self, symbol: str) -> CompanyProfile | None:
        if not self.enabled:
            return None

        bare, exchange = resolve_exchange_symbol(symbol)
        try:
            raw = await self._provider.call_tool("get_company_profile", {"symbol": bare})
            return _parse_company_profile(raw, bare, exchange)
        except TapetideMcpServiceError as exc:
            logger.debug("Tapetide profile unavailable for %s: %s", bare, exc)
            return None

    async def get_market_data(self, symbol: str) -> MarketData | None:
        try:
            quote = await self.get_quote(symbol, allow_yahoo_fallback=False)
        except TapetideMcpServiceError:
            return None

        if quote.last_price is None:
            return None

        return MarketData(
            current_price=quote.last_price,
            previous_close=quote.previous_close or quote.close,
            day_high=quote.high,
            day_low=quote.low,
            volume=quote.volume,
            currency=quote.currency,
        )

    async def get_live_price(self, symbol: str) -> tuple[float | None, str]:
        if not self.enabled:
            return None, YAHOO_SOURCE
        try:
            quote = await self.get_quote(symbol, allow_yahoo_fallback=False)
            if quote.last_price is not None:
                return quote.last_price, TAPETIDE_MCP_SOURCE
        except TapetideMcpServiceError as exc:
            logger.debug("Tapetide live price unavailable for %s: %s", symbol, exc)

        if self._yahoo is not None:
            yahoo_symbol = normalize_indian_ticker(symbol)
            price = await self._yahoo.get_current_price(yahoo_symbol)
            return price, YAHOO_SOURCE

        return None, YAHOO_SOURCE

    async def _yahoo_quote_fallback(
        self,
        symbol: str,
        bare: str,
        exchange: str,
    ) -> TapetideQuoteResponse:
        if self._yahoo is None:
            raise TapetideMcpServiceError("Yahoo fallback provider is not configured")

        yahoo_symbol = normalize_indian_ticker(symbol)
        price = await self._yahoo.get_current_price(yahoo_symbol)
        market = await self._yahoo.get_market_data(yahoo_symbol)

        previous_close = market.previous_close if market else None
        change = None
        change_percent = None
        if price is not None and previous_close not in (None, 0):
            change = price - previous_close
            change_percent = (change / previous_close) * 100

        return TapetideQuoteResponse(
            symbol=normalize_indian_ticker(symbol),
            exchange=exchange,
            last_price=price,
            high=market.day_high if market else None,
            low=market.day_low if market else None,
            close=previous_close,
            previous_close=previous_close,
            volume=market.volume if market else None,
            change=change,
            change_percent=change_percent,
            source=YAHOO_SOURCE,
        )

    async def _yahoo_history_fallback(
        self,
        symbol: str,
        *,
        bare: str,
        exchange: str,
        interval: str,
        from_date: str | None,
        to_date: str | None,
    ) -> TapetideHistoryResponse:
        if self._yahoo is None:
            raise TapetideMcpServiceError("Yahoo fallback provider is not configured")

        yahoo_symbol = normalize_indian_ticker(symbol)
        yf_interval = yahoo_interval_for(interval)
        points = await self._yahoo.get_historical_candles(
            yahoo_symbol,
            interval=yf_interval,
            start=from_date,
            end=to_date,
        )
        points = filter_candles_by_date(points, from_date=from_date, to_date=to_date)
        return TapetideHistoryResponse(
            symbol=normalize_indian_ticker(symbol),
            exchange=exchange,
            interval=interval,
            candles=points,
            source=YAHOO_SOURCE,
        )


def _tapetide_interval(interval: str) -> str:
    normalized = interval.lower().strip()
    if normalized in {"week", "weekly", "1wk"}:
        return "weekly"
    return "daily"


def _default_history_range(
    from_date: str | None,
    to_date: str | None,
) -> tuple[str, str]:
    now = datetime.now(UTC)
    resolved_to = to_date or now.strftime("%Y-%m-%d")
    resolved_from = from_date or (now - timedelta(days=365)).strftime("%Y-%m-%d")
    return resolved_from, resolved_to


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        return raw[0]
    return {}


def _coerce_items(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("results", "data", "stocks", "symbols", "items", "matches"):
            value = raw.get(key)
            if isinstance(value, list):
                return value
        return [raw]
    return []


def _parse_search_results(raw: Any, *, limit: int) -> list[CompanySearchResult]:
    items = _coerce_items(raw)
    results: list[CompanySearchResult] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        symbol = str(
            item.get("symbol")
            or item.get("ticker")
            or item.get("nse_symbol")
            or item.get("bse_symbol")
            or ""
        ).strip()
        if not symbol:
            continue

        company_name = str(
            item.get("company_name")
            or item.get("name")
            or item.get("companyName")
            or symbol
        ).strip()
        exchange = str(item.get("exchange") or item.get("market") or "NSE").upper()
        if exchange not in {"NSE", "BSE"}:
            exchange = "NSE"

        sector = item.get("sector") or item.get("industry")
        results.append(
            CompanySearchResult(
                symbol=symbol.upper().replace(".NS", "").replace(".BO", ""),
                exchange=exchange,
                company_name=company_name,
                sector=str(sector) if sector else None,
                source=TAPETIDE_MCP_SOURCE,
            )
        )
        if len(results) >= limit:
            break

    return results


def _parse_quote_payload(raw: Any, bare: str, exchange: str) -> TapetideQuoteResponse:
    data = _coerce_dict(raw)
    nested = data.get("quote") if isinstance(data.get("quote"), dict) else data

    last_price = _as_float(
        nested.get("ltp")
        or nested.get("last_price")
        or nested.get("lastPrice")
        or nested.get("price")
        or nested.get("current_price")
        or data.get("ltp")
        or data.get("last_price")
    )
    previous_close = _as_float(
        nested.get("previous_close")
        or nested.get("previousClose")
        or nested.get("prev_close")
        or data.get("previous_close")
    )
    open_price = _as_float(nested.get("open") or data.get("open"))
    high = _as_float(nested.get("high") or nested.get("day_high") or data.get("high"))
    low = _as_float(nested.get("low") or nested.get("day_low") or data.get("low"))
    close = previous_close or _as_float(nested.get("close") or data.get("close"))
    volume = _as_int(nested.get("volume") or data.get("volume"))

    change = None
    change_percent = None
    if last_price is not None and previous_close not in (None, 0):
        change = last_price - previous_close
        change_percent = (change / previous_close) * 100

    return TapetideQuoteResponse(
        symbol=normalize_indian_ticker(f"{bare}.{'BO' if exchange == 'BSE' else 'NS'}"),
        exchange=exchange,
        last_price=last_price,
        open=open_price,
        high=high,
        low=low,
        close=close,
        previous_close=previous_close,
        volume=volume,
        change=change,
        change_percent=change_percent,
        source=TAPETIDE_MCP_SOURCE,
    )


def _parse_company_profile(raw: Any, bare: str, exchange: str) -> CompanyProfile | None:
    data = _coerce_dict(raw)
    if not data:
        return None

    profile = data.get("profile") if isinstance(data.get("profile"), dict) else data
    company_name = str(
        profile.get("company_name")
        or profile.get("name")
        or profile.get("companyName")
        or bare
    )
    sector = profile.get("sector") or profile.get("industry")
    industry = profile.get("industry") or profile.get("sector")
    market_cap = _as_float(profile.get("market_cap") or profile.get("marketCap"))
    price = _as_float(profile.get("price") or profile.get("ltp") or profile.get("last_price"))

    return CompanyProfile(
        symbol=normalize_indian_ticker(f"{bare}.{'BO' if exchange == 'BSE' else 'NS'}"),
        company_name=company_name,
        exchange=exchange,
        sector=str(sector) if sector else None,
        industry=str(industry) if industry else None,
        market_cap=market_cap,
        price=price,
        currency="INR",
        description=profile.get("description") or profile.get("about"),
    )


def _parse_history_candles(raw: Any) -> list[HistoricalPricePoint]:
    items = _coerce_items(raw)
    if not items and isinstance(raw, dict):
        items = _coerce_items(raw.get("history") or raw.get("candles") or raw.get("prices"))

    points: list[HistoricalPricePoint] = []
    for item in items:
        if isinstance(item, list) and len(item) >= 5:
            points.append(
                HistoricalPricePoint(
                    date=str(item[0])[:10],
                    open=_as_float(item[1]),
                    high=_as_float(item[2]),
                    low=_as_float(item[3]),
                    close=_as_float(item[4]),
                    volume=_as_int(item[5]) if len(item) > 5 else None,
                )
            )
        elif isinstance(item, dict):
            points.append(
                HistoricalPricePoint(
                    date=str(item.get("date") or item.get("timestamp") or "")[:10],
                    open=_as_float(item.get("open")),
                    high=_as_float(item.get("high")),
                    low=_as_float(item.get("low")),
                    close=_as_float(item.get("close")),
                    volume=_as_int(item.get("volume")),
                )
            )
    return points
