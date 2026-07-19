"""Normalize Kite MCP holdings into portfolio research format."""

from __future__ import annotations

from app.schemas.kite import KiteHoldingItem
from app.schemas.portfolio import PortfolioHolding, PortfolioHoldingsResponse
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
        symbol_resolver: SymbolResolverService | None = None,
    ) -> None:
        self._kite = kite_service
        self._resolver = symbol_resolver or get_symbol_resolver_service()

    async def get_holdings(self) -> PortfolioHoldingsResponse:
        cached = ttl_cache.get("holdings", "kite")
        if cached is not None:
            return cached

        async with async_timed_operation("portfolio.get_holdings"):
            response = await self._get_holdings_uncached()
        ttl_cache.set("holdings", "kite", response)
        return response

    async def _get_holdings_uncached(self) -> PortfolioHoldingsResponse:
        if not self._kite.enabled:
            return PortfolioHoldingsResponse(
                holdings=[],
                auth_required=False,
                message=DISABLED_MESSAGE,
                source=None,
            )

        status = await self._kite.get_status()
        if not status.authenticated or not status.connected:
            return PortfolioHoldingsResponse(
                holdings=[],
                auth_required=True,
                message=status.message or AUTH_REQUIRED_MESSAGE,
                source=KITE_SOURCE,
            )

        try:
            raw = await self._kite.get_holdings()
            holdings = [_normalize_holding(item, self._resolver) for item in raw.holdings]
            return PortfolioHoldingsResponse(
                holdings=holdings,
                auth_required=False,
                message=None,
                source=raw.source,
            )
        except Exception as exc:
            logger.warning("Kite holdings fetch failed: %s", exc)
            return PortfolioHoldingsResponse(
                holdings=[],
                auth_required=True,
                message=AUTH_REQUIRED_MESSAGE,
                source=KITE_SOURCE,
            )


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
