"""Kite MCP service – read-only market data and portfolio access with Yahoo fallback."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.providers.kite_mcp_provider import KiteMcpProvider
from app.providers.kite_symbols import from_kite_symbol, to_kite_symbol
from app.providers.yahoo_finance_provider import YahooFinanceProvider
from app.schemas.financial import HistoricalPricePoint
from app.schemas.kite import (
    KiteHistoryResponse,
    KiteHoldingItem,
    KiteHoldingsResponse,
    KitePositionItem,
    KitePositionsResponse,
    KiteQuoteResponse,
    KiteStatusResponse,
)
from app.services.kite_auth_service import KiteAuthService
from app.utils.exceptions import KiteAuthError, KiteNotEnabledError, KiteServiceError
from app.utils.history_timeframe import filter_candles_by_date, yahoo_interval_for
from app.utils.logging import get_logger

logger = get_logger(__name__)

KITE_SOURCE = "Kite Connect"
YAHOO_SOURCE = "Yahoo Finance"
DISABLED_MESSAGE = "Kite Connect is not enabled."
AUTH_REQUIRED_MESSAGE = "Kite is enabled but Zerodha authentication is required."


class KiteService:
    """Business layer for Kite MCP with read-only guardrails and Yahoo fallback."""

    def __init__(
        self,
        settings: Settings,
        provider: KiteMcpProvider | None = None,
        yahoo_provider: YahooFinanceProvider | None = None,
        auth_service: KiteAuthService | None = None,
    ) -> None:
        self._settings = settings
        self._provider = provider or KiteMcpProvider(settings)
        self._yahoo = yahoo_provider
        self._auth = auth_service

    @property
    def enabled(self) -> bool:
        return self._settings.kite_mcp_enabled

    @property
    def read_only(self) -> bool:
        return self._settings.kite_mcp_read_only

    def assert_enabled(self) -> None:
        if not self.enabled:
            raise KiteNotEnabledError(DISABLED_MESSAGE)

    async def get_status(self) -> KiteStatusResponse:
        if not self.enabled:
            return KiteStatusResponse(
                enabled=False,
                read_only=self.read_only,
                authenticated=False,
                connected=False,
                message=DISABLED_MESSAGE,
                excluded_tools=self._settings.kite_excluded_tools_list,
            )

        authenticated = False
        connected = False
        user_id: str | None = None
        broker: str | None = None
        message = AUTH_REQUIRED_MESSAGE

        if self._auth:
            if self._auth.is_authenticated():
                authenticated = await self._auth.validate_session()
            if authenticated:
                connected = True
                user_id = self._auth.get_user_id()
                broker = self._auth.get_broker()
                message = f"Connected to Zerodha as {user_id}."
            elif not self._auth.is_configured():
                message = "Configure KITE_API_KEY and KITE_API_SECRET for Zerodha OAuth."

        discovered: list[dict[str, Any]] = []
        try:
            discovered = await self._provider.list_tools()
        except KiteServiceError as exc:
            logger.debug("Kite MCP tools probe: %s", exc)

        return KiteStatusResponse(
            enabled=True,
            read_only=self.read_only,
            authenticated=authenticated,
            connected=connected,
            user_id=user_id,
            broker=broker,
            message=message,
            mcp_url=self._settings.kite_mcp_url,
            excluded_tools=self._settings.kite_excluded_tools_list,
            available_read_tools=self._provider.available_read_tools(discovered),
        )

    async def get_quote(self, symbol: str, *, allow_yahoo_fallback: bool = True) -> KiteQuoteResponse:
        self.assert_enabled()
        kite_symbol = to_kite_symbol(symbol)

        if self._auth and self._auth.is_authenticated():
            try:
                quotes = await self._auth.connect_client.get_quotes([kite_symbol])
                parsed = _parse_quote_payload(quotes, kite_symbol)
                if parsed.last_price is not None:
                    parsed.source = KITE_SOURCE
                    return parsed
            except KiteAuthError:
                raise
            except Exception as exc:
                logger.warning("Kite Connect quote failed for %s: %s", kite_symbol, exc)

        try:
            raw = await self._provider.call_tool(
                "get_quotes",
                {"instruments": [kite_symbol]},
            )
            parsed = _parse_quote_payload(raw, kite_symbol)
            if parsed.last_price is not None:
                return parsed
        except Exception as exc:
            logger.warning("Kite MCP quote failed for %s: %s", kite_symbol, exc)
            if not allow_yahoo_fallback:
                raise KiteServiceError(f"Kite quote unavailable for {symbol}") from exc

        if allow_yahoo_fallback and self._yahoo is not None:
            return await self._yahoo_quote_fallback(symbol, kite_symbol)

        raise KiteServiceError(f"Quote unavailable for {symbol}")

    async def get_history(
        self,
        symbol: str,
        *,
        interval: str = "day",
        from_date: str | None = None,
        to_date: str | None = None,
        allow_yahoo_fallback: bool = True,
    ) -> KiteHistoryResponse:
        kite_symbol = to_kite_symbol(symbol)

        if self.enabled:
            arguments: dict[str, Any] = {
                "instrument_token": kite_symbol,
                "interval": interval,
            }
            if from_date:
                arguments["from_date"] = from_date
            if to_date:
                arguments["to_date"] = to_date

            try:
                raw = await self._provider.call_tool("get_historical_data", arguments)
                candles = _parse_history_candles(raw)
                if candles:
                    return KiteHistoryResponse(
                        symbol=from_kite_symbol(kite_symbol),
                        kite_symbol=kite_symbol,
                        interval=interval,
                        candles=candles,
                        source=KITE_SOURCE,
                    )
            except Exception as exc:
                logger.warning("Kite history failed for %s: %s", kite_symbol, exc)
                if not allow_yahoo_fallback:
                    raise KiteServiceError(f"Kite history unavailable for {symbol}") from exc

        if allow_yahoo_fallback and self._yahoo is not None:
            return await self._yahoo_history_fallback(
                symbol,
                kite_symbol=kite_symbol,
                interval=interval,
                from_date=from_date,
                to_date=to_date,
            )

        return KiteHistoryResponse(
            symbol=from_kite_symbol(kite_symbol),
            kite_symbol=kite_symbol,
            interval=interval,
            candles=[],
            source=KITE_SOURCE if self.enabled else YAHOO_SOURCE,
        )

    async def _yahoo_history_fallback(
        self,
        symbol: str,
        *,
        kite_symbol: str,
        interval: str,
        from_date: str | None,
        to_date: str | None,
    ) -> KiteHistoryResponse:
        if self._yahoo is None:
            raise KiteServiceError("Yahoo fallback provider is not configured")

        yahoo_symbol = _to_yahoo_symbol(symbol)
        yf_interval = yahoo_interval_for(interval)
        points = await self._yahoo.get_historical_candles(
            yahoo_symbol,
            interval=yf_interval,
            start=from_date,
            end=to_date,
        )
        points = filter_candles_by_date(points, from_date=from_date, to_date=to_date)
        return KiteHistoryResponse(
            symbol=from_kite_symbol(kite_symbol),
            kite_symbol=kite_symbol,
            interval=interval,
            candles=points,
            source=YAHOO_SOURCE,
        )

    async def get_holdings(self) -> KiteHoldingsResponse:
        self.assert_enabled()
        if self._auth and self._auth.is_authenticated():
            holdings = await self._auth.connect_client.get_holdings()
            return KiteHoldingsResponse(holdings=holdings, source=KITE_SOURCE)

        raise KiteAuthError(AUTH_REQUIRED_MESSAGE)

    async def get_positions(self) -> KitePositionsResponse:
        self.assert_enabled()
        if self._auth and self._auth.is_authenticated():
            net, day = await self._auth.connect_client.get_positions()
            return KitePositionsResponse(net=net, day=day, source=KITE_SOURCE)

        raise KiteAuthError(AUTH_REQUIRED_MESSAGE)

    async def get_live_price(self, symbol: str) -> tuple[float | None, str]:
        """Return (price, source) for FinancialDataService – silent Yahoo fallback."""
        if self.enabled:
            try:
                quote = await self.get_quote(symbol, allow_yahoo_fallback=False)
                if quote.last_price is not None:
                    return quote.last_price, KITE_SOURCE
            except Exception as exc:
                logger.debug("Kite live price fallback for %s: %s", symbol, exc)

        if self._yahoo is not None:
            yahoo_symbol = _to_yahoo_symbol(symbol)
            price = await self._yahoo.get_current_price(yahoo_symbol)
            return price, YAHOO_SOURCE

        return None, YAHOO_SOURCE

    async def _yahoo_quote_fallback(self, symbol: str, kite_symbol: str) -> KiteQuoteResponse:
        if self._yahoo is None:
            raise KiteServiceError("Yahoo fallback provider is not configured")

        yahoo_symbol = _to_yahoo_symbol(symbol)
        price = await self._yahoo.get_current_price(yahoo_symbol)
        market = await self._yahoo.get_market_data(yahoo_symbol)

        return KiteQuoteResponse(
            symbol=from_kite_symbol(kite_symbol),
            kite_symbol=kite_symbol,
            exchange=_extract_exchange(kite_symbol, {}),
            last_price=price,
            high=market.day_high if market else None,
            low=market.day_low if market else None,
            close=market.previous_close if market else None,
            volume=market.volume if market else None,
            source=YAHOO_SOURCE,
        )


def _to_yahoo_symbol(symbol: str) -> str:
    from app.providers.ticker import normalize_indian_ticker

    return normalize_indian_ticker(symbol)


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


def _parse_quote_payload(raw: Any, kite_symbol: str) -> KiteQuoteResponse:
    data = raw
    if isinstance(raw, str):
        import json

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

    quote: dict[str, Any] = {}
    if isinstance(data, dict):
        if kite_symbol in data and isinstance(data[kite_symbol], dict):
            quote = data[kite_symbol]
        elif data:
            first = next(iter(data.values()))
            quote = first if isinstance(first, dict) else data
    elif isinstance(data, list) and data:
        quote = data[0] if isinstance(data[0], dict) else {}

    ohlc = quote.get("ohlc") if isinstance(quote.get("ohlc"), dict) else {}
    last_price = _as_float(quote.get("last_price") or quote.get("last_traded_price") or quote.get("ltp"))
    close = _as_float(ohlc.get("close") or quote.get("close"))
    change = None
    change_percent = None
    if last_price is not None and close not in (None, 0):
        change = last_price - close
        change_percent = (change / close) * 100

    return KiteQuoteResponse(
        symbol=from_kite_symbol(kite_symbol),
        kite_symbol=kite_symbol,
        exchange=_extract_exchange(kite_symbol, quote),
        last_price=last_price,
        open=_as_float(ohlc.get("open") or quote.get("open")),
        high=_as_float(ohlc.get("high") or quote.get("high")),
        low=_as_float(ohlc.get("low") or quote.get("low")),
        close=close,
        volume=_as_int(quote.get("volume")),
        change=change,
        change_percent=change_percent,
        source=KITE_SOURCE,
    )


def _parse_history_candles(raw: Any) -> list[HistoricalPricePoint]:
    candles_raw: list[Any] = []
    if isinstance(raw, dict):
        candles_raw = raw.get("candles") or raw.get("data") or []
    elif isinstance(raw, list):
        candles_raw = raw

    points: list[HistoricalPricePoint] = []
    for item in candles_raw:
        if isinstance(item, list) and len(item) >= 5:
            date_val = str(item[0])
            points.append(
                HistoricalPricePoint(
                    date=date_val,
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
                    date=str(item.get("date") or item.get("timestamp") or ""),
                    open=_as_float(item.get("open")),
                    high=_as_float(item.get("high")),
                    low=_as_float(item.get("low")),
                    close=_as_float(item.get("close")),
                    volume=_as_int(item.get("volume")),
                )
            )
    return points


def _extract_exchange(kite_symbol: str, quote: dict[str, Any]) -> str | None:
    if quote.get("exchange"):
        return str(quote["exchange"])
    if ":" in kite_symbol:
        return kite_symbol.split(":", 1)[0]
    return None


def _parse_holdings(raw: Any) -> list[KiteHoldingItem]:
    items: list[Any]
    if isinstance(raw, dict):
        items = raw.get("holdings") or raw.get("data") or []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []

    holdings: list[KiteHoldingItem] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        holdings.append(
            KiteHoldingItem(
                tradingsymbol=str(item.get("tradingsymbol") or item.get("symbol") or ""),
                exchange=item.get("exchange"),
                quantity=_as_float(item.get("quantity")),
                average_price=_as_float(item.get("average_price")),
                last_price=_as_float(item.get("last_price")),
                pnl=_as_float(item.get("pnl")),
                product=item.get("product"),
                company_name=item.get("company_name") or item.get("name"),
                sector=item.get("sector"),
                day_change=_as_float(
                    item.get("day_change")
                    or item.get("day_change_percentage")
                    or item.get("day_change_percent")
                ),
            )
        )
    return holdings


def _parse_positions(raw: Any) -> tuple[list[KitePositionItem], list[KitePositionItem]]:
    if isinstance(raw, dict):
        net_raw = raw.get("net") or []
        day_raw = raw.get("day") or []
    else:
        net_raw = []
        day_raw = []

    def _map(items: list[Any]) -> list[KitePositionItem]:
        mapped: list[KitePositionItem] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            mapped.append(
                KitePositionItem(
                    tradingsymbol=str(item.get("tradingsymbol") or item.get("symbol") or ""),
                    exchange=item.get("exchange"),
                    quantity=_as_float(item.get("quantity")),
                    average_price=_as_float(item.get("average_price")),
                    last_price=_as_float(item.get("last_price")),
                    pnl=_as_float(item.get("pnl")),
                    product=item.get("product"),
                )
            )
        return mapped

    return _map(net_raw if isinstance(net_raw, list) else []), _map(
        day_raw if isinstance(day_raw, list) else []
    )
