"""Normalize Kite + Groww holdings into one combined portfolio research format."""

from __future__ import annotations

from app.schemas.groww import GrowwHoldingItem
from app.schemas.kite import KiteHoldingItem
from app.schemas.portfolio import PortfolioHolding, PortfolioHoldingsResponse
from app.services.groww_service import GROWW_SOURCE, GrowwService
from app.services.kite_service import KITE_SOURCE, KiteService
from app.services.symbol_resolver_service import SymbolResolverService, get_symbol_resolver_service
from app.utils.logging import get_logger
from app.utils import ttl_cache
from app.utils.timing import async_timed_operation

logger = get_logger(__name__)

AUTH_REQUIRED_MESSAGE = "Kite is enabled but Zerodha authentication is required."
DISABLED_MESSAGE = "Kite Connect is not enabled."


class PortfolioHoldingsService:
    def __init__(
        self,
        kite_service: KiteService,
        groww_service: GrowwService | None = None,
        symbol_resolver: SymbolResolverService | None = None,
    ) -> None:
        self._kite = kite_service
        self._groww = groww_service
        self._resolver = symbol_resolver or get_symbol_resolver_service()

    async def get_holdings(self) -> PortfolioHoldingsResponse:
        cached = ttl_cache.get("holdings", "portfolio")
        if cached is not None:
            return cached

        async with async_timed_operation("portfolio.get_holdings"):
            response = await self._get_holdings_uncached()
        ttl_cache.set("holdings", "portfolio", response)
        return response

    async def _get_holdings_uncached(self) -> PortfolioHoldingsResponse:
        kite_holdings, kite_message, kite_auth_required, kite_source = await self._get_kite_holdings()
        groww_holdings, groww_message = await self._get_groww_holdings()

        combined = kite_holdings + groww_holdings
        if combined:
            # Prefer surfacing a Groww-specific note only when Kite has nothing
            # to say, so a broker outage on one side doesn't drown out the
            # other broker's holdings actually being present.
            message = kite_message or groww_message
            sources = [
                s
                for s in (
                    kite_source if kite_holdings else None,
                    GROWW_SOURCE if groww_holdings else None,
                )
                if s
            ]
            return PortfolioHoldingsResponse(
                holdings=combined,
                auth_required=False,
                message=message,
                source=", ".join(sources) if sources else None,
            )

        return PortfolioHoldingsResponse(
            holdings=[],
            auth_required=kite_auth_required,
            message=kite_message or groww_message,
            source=kite_source,
        )

    async def _get_kite_holdings(self) -> tuple[list[PortfolioHolding], str | None, bool, str | None]:
        if not self._kite.enabled:
            return [], DISABLED_MESSAGE, False, None

        status = await self._kite.get_status()
        if not status.authenticated or not status.connected:
            return [], status.message or AUTH_REQUIRED_MESSAGE, True, KITE_SOURCE

        try:
            raw = await self._kite.get_holdings()
            holdings = [_normalize_holding(item, self._resolver) for item in raw.holdings]
            return holdings, None, False, raw.source
        except Exception as exc:
            logger.warning("Kite holdings fetch failed: %s", exc)
            return [], AUTH_REQUIRED_MESSAGE, True, KITE_SOURCE

    async def _get_groww_holdings(self) -> tuple[list[PortfolioHolding], str | None]:
        if self._groww is None or not self._groww.enabled:
            return [], None

        try:
            raw = await self._groww.get_holdings()
            holdings = [_normalize_groww_holding(item, self._resolver) for item in raw.holdings]
            return holdings, None
        except Exception as exc:
            logger.warning("Groww holdings fetch failed: %s", exc)
            return [], str(exc)


def _normalize_holding(item: KiteHoldingItem, resolver: SymbolResolverService) -> PortfolioHolding:
    resolved = resolver.resolve_bare(item.tradingsymbol, exchange=item.exchange)
    company_name = resolved.company_name if resolved else item.company_name
    exchange = resolved.exchange if resolved else item.exchange
    qty = item.quantity
    avg = item.average_price
    last = item.last_price
    invested = (qty * avg) if qty is not None and avg is not None else None
    current = (qty * last) if qty is not None and last is not None else None
    pnl = item.pnl
    pnl_percent = None
    if pnl is not None and invested not in (None, 0):
        pnl_percent = (pnl / invested) * 100

    return PortfolioHolding(
        symbol=item.tradingsymbol,
        exchange=exchange,
        company_name=company_name,
        quantity=qty,
        average_price=avg,
        last_price=last,
        invested_value=invested,
        current_value=current,
        pnl=pnl,
        pnl_percent=pnl_percent,
        day_change=item.day_change,
        sector=item.sector,
        price_source="kite",
    )


def _normalize_groww_holding(item: GrowwHoldingItem, resolver: SymbolResolverService) -> PortfolioHolding:
    resolved = resolver.resolve_bare(item.trading_symbol, exchange=item.exchange)
    company_name = resolved.company_name if resolved else None
    exchange = resolved.exchange if resolved else item.exchange
    qty = item.quantity
    avg = item.average_price
    last = item.last_price
    invested = (qty * avg) if qty is not None and avg is not None else None
    current = (qty * last) if qty is not None and last is not None else None
    pnl = item.pnl
    pnl_percent = None
    if pnl is not None and invested not in (None, 0):
        pnl_percent = (pnl / invested) * 100

    return PortfolioHolding(
        symbol=item.trading_symbol,
        exchange=exchange,
        company_name=company_name,
        quantity=qty,
        average_price=avg,
        last_price=last,
        invested_value=invested,
        current_value=current,
        pnl=pnl,
        pnl_percent=pnl_percent,
        day_change=None,
        sector=None,
        price_source="groww",
    )
