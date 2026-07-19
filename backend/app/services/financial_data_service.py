"""
Financial Data Service – business logic layer for structured market data.

Flow:
    FastAPI route / CrewAI tool
        -> FinancialDataService
        -> Tapetide MCP (optional) / Kite (optional) / Yahoo Finance fallback
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from app.providers.base import FinancialDataProvider
from app.providers.data_sources import (
    TAPETIDE_MCP_SOURCE,
    YAHOO_SOURCE,
    normalize_source_slug,
)
from app.providers.ticker import normalize_indian_ticker
from app.services.kite_service import KiteService
from app.services.tapetide_service import TapetideService
from app.services.symbol_resolver_service import SymbolResolverService, get_symbol_resolver_service
from app.schemas.financial import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    DataCollectionWarning,
    FinancialRatios,
    FinancialResearchResponse,
    FinancialSummaryResponse,
    HistoricalPricePoint,
    IncomeStatement,
    KeyMetrics,
    MarketData,
)
from app.schemas.history import HistoricalCandle
from app.utils.candle_format import to_historical_candles
from app.utils.exceptions import InvestIQError, TickerNotFoundError
from app.utils.history_timeframe import yahoo_interval_for
from app.utils.logging import get_logger
from app.utils import ttl_cache
from app.utils.timing import async_timed_operation

logger = get_logger(__name__)


@dataclass
class PriceHistoryResult:
    candles: list[HistoricalCandle]
    source: str


class FinancialDataService:
    """Collects structured financial facts for Indian equities via providers."""

    def __init__(
        self,
        provider: FinancialDataProvider,
        kite_service: KiteService | None = None,
        tapetide_service: TapetideService | None = None,
        symbol_resolver: SymbolResolverService | None = None,
    ) -> None:
        self._provider = provider
        self._kite = kite_service
        self._tapetide = tapetide_service
        self._resolver = symbol_resolver or get_symbol_resolver_service()

    def _resolve_ticker(self, ticker: str) -> str:
        cleaned = ticker.strip()
        if not cleaned:
            raise TickerNotFoundError("Ticker symbol is required")

        resolved = self._resolver.resolve_query(cleaned)
        if resolved:
            normalized = self._resolver.to_yahoo_ticker(resolved)
            logger.info(
                "Resolved ticker %s -> %s (%s)",
                ticker,
                normalized,
                resolved.company_name,
            )
            return normalized

        normalized = normalize_indian_ticker(cleaned)
        logger.info("Resolved ticker %s -> %s (provider fallback)", ticker, normalized)
        return normalized

    async def get_company_profile(self, ticker: str) -> CompanyProfile:
        symbol = self._resolve_ticker(ticker)
        profile, _ = await self._resolve_profile(symbol)
        return profile

    async def get_current_price(self, ticker: str) -> float | None:
        symbol = self._resolve_ticker(ticker)
        price, _ = await self._resolve_live_price(symbol)
        if price is not None:
            return price
        return await self._provider.get_current_price(symbol)

    async def get_income_statement(self, ticker: str) -> list[IncomeStatement]:
        symbol = self._resolve_ticker(ticker)
        return await self._provider.get_income_statement(symbol)

    async def get_balance_sheet(self, ticker: str) -> list[BalanceSheet]:
        symbol = self._resolve_ticker(ticker)
        return await self._provider.get_balance_sheet(symbol)

    async def get_cash_flow(self, ticker: str) -> list[CashFlowStatement]:
        symbol = self._resolve_ticker(ticker)
        return await self._provider.get_cash_flow(symbol)

    async def get_financial_ratios(self, ticker: str) -> list[FinancialRatios]:
        symbol = self._resolve_ticker(ticker)
        return await self._provider.get_financial_ratios(symbol)

    async def get_historical_prices(
        self, ticker: str, period: str = "5y"
    ) -> list[HistoricalPricePoint]:
        symbol = self._resolve_ticker(ticker)
        return await self._provider.get_historical_prices(symbol, period=period)

    async def get_price_history(
        self,
        ticker: str,
        *,
        interval: str = "day",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[HistoricalCandle]:
        result = await self.get_price_history_with_source(
            ticker,
            interval=interval,
            from_date=from_date,
            to_date=to_date,
        )
        return result.candles

    async def get_price_history_with_source(
        self,
        ticker: str,
        *,
        interval: str = "day",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> PriceHistoryResult:
        """
        OHLC history for charting.

        Priority: Tapetide MCP -> Kite -> Yahoo Finance.
        """
        symbol = self._resolve_ticker(ticker)
        cache_key = f"{symbol}:{interval}:{from_date}:{to_date}"
        cached = ttl_cache.get("history", cache_key)
        if cached is not None:
            return cached

        async with async_timed_operation(
            "financial.get_price_history", ticker=symbol, interval=interval
        ):
            result = await self._get_price_history_uncached(
                ticker,
                symbol=symbol,
                interval=interval,
                from_date=from_date,
                to_date=to_date,
            )
        ttl_cache.set("history", cache_key, result)
        return result

    async def _get_price_history_uncached(
        self,
        ticker: str,
        *,
        symbol: str,
        interval: str,
        from_date: str | None,
        to_date: str | None,
    ) -> PriceHistoryResult:
        if self._tapetide is not None and self._tapetide.enabled:
            try:
                tapetide_result = await self._tapetide.get_history(
                    ticker,
                    interval=interval,
                    from_date=from_date,
                    to_date=to_date,
                    allow_yahoo_fallback=False,
                )
                if tapetide_result.candles:
                    return PriceHistoryResult(
                        candles=to_historical_candles(tapetide_result.candles),
                        source=tapetide_result.source,
                    )
            except Exception as exc:
                logger.warning("Tapetide history unavailable for %s: %s", ticker, exc)

        if self._kite is not None:
            try:
                kite_result = await self._kite.get_history(
                    ticker,
                    interval=interval,
                    from_date=from_date,
                    to_date=to_date,
                    allow_yahoo_fallback=False,
                )
                if kite_result.candles:
                    return PriceHistoryResult(
                        candles=to_historical_candles(kite_result.candles),
                        source=normalize_source_slug(kite_result.source),
                    )
            except Exception as exc:
                logger.warning("Kite history unavailable for %s: %s", ticker, exc)

        yf_interval = yahoo_interval_for(interval)
        points = await self._provider.get_historical_candles(
            symbol,
            interval=yf_interval,
            start=from_date,
            end=to_date,
        )
        return PriceHistoryResult(
            candles=to_historical_candles(points),
            source=YAHOO_SOURCE,
        )

    async def _profile_bundle(self, symbol: str) -> tuple[CompanyProfile, str]:
        return await self._resolve_profile(symbol)

    async def _resolve_profile(self, symbol: str) -> tuple[CompanyProfile, str]:
        """Prefer Tapetide profile overlay; fall back to Yahoo."""
        if self._tapetide is not None and self._tapetide.enabled:
            yahoo_profile, tapetide_profile = await asyncio.gather(
                self._provider.get_company_profile(symbol),
                self._tapetide.get_company_profile(symbol),
            )
            if tapetide_profile is not None:
                return _merge_profiles(yahoo_profile, tapetide_profile), TAPETIDE_MCP_SOURCE
            return yahoo_profile, YAHOO_SOURCE
        profile = await self._provider.get_company_profile(symbol)
        return profile, YAHOO_SOURCE

    async def get_summary(self, ticker: str) -> FinancialSummaryResponse:
        """Return a compact financial snapshot for the test endpoint."""
        symbol = self._resolve_ticker(ticker)
        cached = ttl_cache.get("financial", symbol)
        if cached is not None:
            return cached

        async with async_timed_operation("financial.get_summary", ticker=symbol):
            result = await self._get_summary_uncached(symbol)
        ttl_cache.set("financial", symbol, result)
        return result

    async def _get_summary_uncached(self, symbol: str) -> FinancialSummaryResponse:
        profile_bundle, ratios, metrics, market_data, supplemental = await asyncio.gather(
            self._profile_bundle(symbol),
            self._provider.get_financial_ratios(symbol),
            self._provider.get_key_metrics(symbol),
            self._provider.get_market_data(symbol),
            self._provider.get_supplemental_metrics(symbol),
            return_exceptions=True,
        )

        if isinstance(profile_bundle, Exception):
            raise profile_bundle if isinstance(profile_bundle, InvestIQError) else TickerNotFoundError(
                f"No financial data found for ticker: {symbol}"
            )

        profile, fundamentals_source = profile_bundle
        ratio_row = ratios[0] if isinstance(ratios, list) and ratios else None
        metric_row = metrics[0] if isinstance(metrics, list) and metrics else None
        market = market_data if isinstance(market_data, MarketData) else None
        extra = supplemental if isinstance(supplemental, dict) else {}

        current_price = (market.current_price if market else None) or profile.price
        price_source = YAHOO_SOURCE

        if self._tapetide is not None and self._tapetide.enabled:
            tapetide_price, tapetide_source = await self._tapetide.get_live_price(symbol)
            if tapetide_price is not None:
                current_price = tapetide_price
                price_source = tapetide_source

        if self._kite is not None:
            kite_price, kite_source = await self._kite.get_live_price(symbol)
            if kite_price is not None:
                current_price = kite_price
                price_source = normalize_source_slug(kite_source)

        return FinancialSummaryResponse(
            ticker=symbol,
            company_name=profile.company_name or "",
            sector=profile.sector or "",
            industry=profile.industry or "",
            market_cap=profile.market_cap,
            current_price=current_price,
            currency=(profile.currency or (market.currency if market else None) or "INR"),
            pe_ratio=(metric_row.pe_ratio if metric_row else None)
            or (ratio_row.price_to_earnings if ratio_row else None),
            pb_ratio=(metric_row.pb_ratio if metric_row else None)
            or (ratio_row.price_to_book if ratio_row else None),
            roe=ratio_row.return_on_equity if ratio_row else None,
            debt_to_equity=ratio_row.debt_to_equity if ratio_row else None,
            revenue_growth=extra.get("revenue_growth"),
            profit_margin=ratio_row.net_profit_margin if ratio_row else None,
            dividend_yield=extra.get("dividend_yield"),
            data_source=fundamentals_source,
            fundamentals_source=fundamentals_source,
            price_source=price_source,
            data_timestamp=datetime.now(UTC),
        )

    async def collect(self, ticker: str) -> FinancialResearchResponse:
        """Full structured collection used by research pipeline and agents."""
        symbol = self._resolve_ticker(ticker)
        cached = ttl_cache.get("financial", f"collect:{symbol}")
        if cached is not None:
            return cached

        async with async_timed_operation("financial.collect", ticker=symbol):
            result = await self._collect_uncached(symbol)
        ttl_cache.set("financial", f"collect:{symbol}", result)
        return result

    async def _collect_uncached(self, symbol: str) -> FinancialResearchResponse:
        warnings: list[DataCollectionWarning] = []
        data_sources: list[str] = [self._provider.name]

        results = await asyncio.gather(
            self._provider.get_company_profile(symbol),
            self._provider.get_income_statement(symbol),
            self._provider.get_balance_sheet(symbol),
            self._provider.get_cash_flow(symbol),
            self._provider.get_financial_ratios(symbol),
            self._provider.get_key_metrics(symbol),
            self._provider.get_market_data(symbol),
            return_exceptions=True,
        )

        (
            profile_result,
            income_result,
            balance_result,
            cashflow_result,
            ratios_result,
            metrics_result,
            market_result,
        ) = results

        if isinstance(profile_result, Exception):
            logger.error("Profile fetch failed for %s: %s", symbol, profile_result)
            raise profile_result if isinstance(profile_result, InvestIQError) else TickerNotFoundError(
                f"No financial data found for ticker: {symbol}"
            )

        profile = profile_result
        if self._tapetide is not None and self._tapetide.enabled:
            exchange_profile = await self._tapetide.get_company_profile(symbol)
            if exchange_profile is not None:
                profile = _merge_profiles(profile, exchange_profile)
                if TAPETIDE_MCP_SOURCE not in data_sources:
                    data_sources.append(TAPETIDE_MCP_SOURCE)

            try:
                tapetide_market = await self._tapetide.get_market_data(symbol)
                if tapetide_market is not None and isinstance(market_result, MarketData):
                    market_result = tapetide_market
                elif tapetide_market is not None and not isinstance(market_result, Exception):
                    market_result = tapetide_market
            except Exception as exc:
                warnings.append(
                    DataCollectionWarning(
                        source=TAPETIDE_MCP_SOURCE,
                        message=f"Tapetide market data unavailable: {exc}",
                    )
                )

        income_statements = _unwrap_or_warn(
            income_result, "income statements", warnings, self._provider.name
        )
        balance_sheets = _unwrap_or_warn(
            balance_result, "balance sheets", warnings, self._provider.name
        )
        cash_flow_statements = _unwrap_or_warn(
            cashflow_result, "cash flow statements", warnings, self._provider.name
        )
        ratios = _unwrap_or_warn(ratios_result, "ratios", warnings, self._provider.name)
        key_metrics = _unwrap_or_warn(metrics_result, "key metrics", warnings, self._provider.name)

        market_data: MarketData | None = None
        if isinstance(market_result, Exception):
            warnings.append(
                DataCollectionWarning(
                    source=self._provider.name,
                    message=f"Failed to fetch market data: {market_result}",
                )
            )
        else:
            market_data = market_result

        if not income_statements:
            warnings.append(
                DataCollectionWarning(
                    source=self._provider.name,
                    message="Income statement data is unavailable for this ticker",
                )
            )
        if not balance_sheets:
            warnings.append(
                DataCollectionWarning(
                    source=self._provider.name,
                    message="Balance sheet data is unavailable for this ticker",
                )
            )

        return FinancialResearchResponse(
            ticker=symbol,
            profile=profile,
            income_statements=income_statements,
            balance_sheets=balance_sheets,
            cash_flow_statements=cash_flow_statements,
            ratios=ratios,
            key_metrics=key_metrics,
            market_data=market_data,
            data_sources=data_sources,
            warnings=warnings,
        )

    async def _resolve_live_price(self, symbol: str) -> tuple[float | None, str]:
        if self._kite is not None:
            kite_price, kite_source = await self._kite.get_live_price(symbol)
            if kite_price is not None:
                return kite_price, normalize_source_slug(kite_source)

        if self._tapetide is not None and self._tapetide.enabled:
            return await self._tapetide.get_live_price(symbol)

        price = await self._provider.get_current_price(symbol)
        return price, YAHOO_SOURCE


def _merge_profiles(base: CompanyProfile, overlay: CompanyProfile) -> CompanyProfile:
    return CompanyProfile(
        symbol=overlay.symbol or base.symbol,
        company_name=overlay.company_name or base.company_name,
        exchange=overlay.exchange or base.exchange,
        sector=overlay.sector or base.sector,
        industry=overlay.industry or base.industry,
        country=overlay.country or base.country,
        currency=overlay.currency or base.currency,
        market_cap=overlay.market_cap or base.market_cap,
        price=overlay.price or base.price,
        beta=overlay.beta or base.beta,
        description=overlay.description or base.description,
        ceo=overlay.ceo or base.ceo,
        website=overlay.website or base.website,
        ipo_date=overlay.ipo_date or base.ipo_date,
    )


def _unwrap_or_warn(
    result: object,
    label: str,
    warnings: list[DataCollectionWarning],
    source: str,
) -> list:
    if isinstance(result, Exception):
        warnings.append(
            DataCollectionWarning(
                source=source,
                message=f"Failed to fetch {label}: {result}",
            )
        )
        return []
    return result
