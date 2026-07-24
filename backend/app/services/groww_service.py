"""Groww Trade API service – read-only holdings/positions/margin with Yahoo price enrichment.

Groww's own live-data endpoints (get_ltp/get_quote) return "Access forbidden"
for this API key — live market data appears to need a separate entitlement
from portfolio/holdings/margin access (verified live against the real
account). Price enrichment for current_value/pnl therefore reuses the same
YahooFinanceProvider KiteService already falls back to, rather than Groww's
own (currently inaccessible) LTP endpoint.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.providers.groww_client import GrowwClient
from app.providers.ticker import normalize_indian_ticker
from app.providers.yahoo_finance_provider import YahooFinanceProvider
from app.schemas.groww import (
    GrowwHoldingItem,
    GrowwHoldingsResponse,
    GrowwPositionItem,
    GrowwPositionsResponse,
    GrowwStatusResponse,
)
from app.utils.exceptions import GrowwNotEnabledError, GrowwServiceError
from app.utils.logging import get_logger

logger = get_logger(__name__)

GROWW_SOURCE = "Groww"
DISABLED_MESSAGE = "Groww integration is not enabled."
CREDENTIALS_MISSING_MESSAGE = "Groww is enabled but GROWW_API_KEY/GROWW_API_SECRET are not configured."


class GrowwService:
    """Business layer for the Groww Trade API with read-only guardrails."""

    def __init__(
        self,
        settings: Settings,
        client: GrowwClient | None = None,
        yahoo_provider: YahooFinanceProvider | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or GrowwClient(settings)
        self._yahoo = yahoo_provider

    @property
    def enabled(self) -> bool:
        return self._settings.groww_enabled

    def assert_enabled(self) -> None:
        if not self.enabled:
            raise GrowwNotEnabledError(DISABLED_MESSAGE)

    async def get_status(self) -> GrowwStatusResponse:
        if not self.enabled:
            return GrowwStatusResponse(
                enabled=False,
                credentials_configured=self._settings.groww_credentials_configured,
                connected=False,
                message=DISABLED_MESSAGE,
            )

        if not self._settings.groww_credentials_configured:
            return GrowwStatusResponse(
                enabled=True,
                credentials_configured=False,
                connected=False,
                message=CREDENTIALS_MISSING_MESSAGE,
            )

        try:
            profile = await self._client.get_profile()
            ucc = profile.get("ucc") or profile.get("vendor_user_id")
            return GrowwStatusResponse(
                enabled=True,
                credentials_configured=True,
                connected=True,
                message=f"Connected to Groww as {ucc}." if ucc else "Connected to Groww.",
            )
        except GrowwServiceError as exc:
            logger.warning("Groww status check failed: %s", exc)
            return GrowwStatusResponse(
                enabled=True,
                credentials_configured=True,
                connected=False,
                message=str(exc),
            )

    async def get_holdings(self) -> GrowwHoldingsResponse:
        self.assert_enabled()
        if not self._settings.groww_credentials_configured:
            raise GrowwNotEnabledError(CREDENTIALS_MISSING_MESSAGE)

        raw = await self._client.get_holdings()
        items = raw.get("holdings") or []
        holdings = [await self._enrich_holding(item) for item in items if isinstance(item, dict)]
        return GrowwHoldingsResponse(holdings=holdings, source=GROWW_SOURCE)

    async def _enrich_holding(self, item: dict[str, Any]) -> GrowwHoldingItem:
        trading_symbol = str(item.get("trading_symbol") or "")
        quantity = _as_float(item.get("quantity"))
        average_price = _as_float(item.get("average_price"))
        exchanges = item.get("tradable_exchanges") or []
        exchange = exchanges[0] if exchanges else "NSE"

        last_price: float | None = None
        if self._yahoo is not None and trading_symbol:
            try:
                yahoo_symbol = normalize_indian_ticker(trading_symbol)
                last_price = await self._yahoo.get_current_price(yahoo_symbol)
            except Exception as exc:
                logger.debug("Yahoo price lookup failed for Groww holding %s: %s", trading_symbol, exc)

        pnl = None
        if quantity is not None and average_price is not None and last_price is not None:
            pnl = (last_price - average_price) * quantity

        return GrowwHoldingItem(
            trading_symbol=trading_symbol,
            isin=item.get("isin"),
            exchange=exchange,
            quantity=quantity,
            average_price=average_price,
            last_price=last_price,
            pnl=pnl,
        )

    async def get_positions(self) -> GrowwPositionsResponse:
        self.assert_enabled()
        if not self._settings.groww_credentials_configured:
            raise GrowwNotEnabledError(CREDENTIALS_MISSING_MESSAGE)

        raw = await self._client.get_positions()
        items = raw.get("positions") or []
        positions = [_parse_position(item) for item in items if isinstance(item, dict)]
        return GrowwPositionsResponse(positions=positions, source=GROWW_SOURCE)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_position(item: dict[str, Any]) -> GrowwPositionItem:
    return GrowwPositionItem(
        trading_symbol=str(item.get("trading_symbol") or ""),
        segment=item.get("segment"),
        quantity=_as_float(item.get("quantity")),
        net_price=_as_float(item.get("net_price")),
        realised_pnl=_as_float(item.get("realised_pnl")),
        product=item.get("product"),
    )
