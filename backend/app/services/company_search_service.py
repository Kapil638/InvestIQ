"""Company search – NSE master first, provider fallback only when needed."""

from __future__ import annotations

import re

from app.core.config import Settings
from app.providers.data_sources import NSE_SOURCE, TAPETIDE_MCP_SOURCE, YAHOO_SOURCE
from app.providers.yahoo_finance_provider import YahooFinanceProvider
from app.schemas.company_search import CompanySearchResponse, CompanySearchResult
from app.services.company_master_service import CompanyMasterService, get_company_master_service
from app.services.symbol_resolver_service import SymbolResolverService, get_symbol_resolver_service
from app.services.tapetide_service import TapetideService
from app.utils.exceptions import TapetideMcpServiceError
from app.utils.logging import get_logger
from app.utils import ttl_cache
from app.utils.timing import async_timed_operation

logger = get_logger(__name__)

DEFAULT_LIMIT = 12
MAX_LIMIT = 15


class CompanySearchService:
    """Search Indian listed companies with NSE master first."""

    def __init__(
        self,
        settings: Settings,
        tapetide_service: TapetideService | None = None,
        yahoo_provider: YahooFinanceProvider | None = None,
        master_service: CompanyMasterService | None = None,
        symbol_resolver: SymbolResolverService | None = None,
    ) -> None:
        self._settings = settings
        self._tapetide = tapetide_service
        self._yahoo = yahoo_provider or (
            YahooFinanceProvider() if settings.yfinance_enabled else None
        )
        self._master = master_service or get_company_master_service()
        self._resolver = symbol_resolver or get_symbol_resolver_service()

    async def search(self, query: str, *, limit: int = DEFAULT_LIMIT) -> CompanySearchResponse:
        cleaned = query.strip()
        capped_limit = max(1, min(limit, MAX_LIMIT))

        if len(cleaned) < 2:
            return CompanySearchResponse(results=[], source=NSE_SOURCE)

        cache_key = f"{cleaned.lower()}:{capped_limit}"
        cached = ttl_cache.get("search", cache_key)
        if cached is not None:
            return cached

        async with async_timed_operation("search.companies", query=cleaned):
            response = await self._search_uncached(cleaned, capped_limit)
        ttl_cache.set("search", cache_key, response)
        return response

    async def _search_uncached(self, cleaned: str, capped_limit: int) -> CompanySearchResponse:
        master_results = self._search_nse_master(cleaned, capped_limit)
        if master_results:
            return CompanySearchResponse(results=master_results, source=NSE_SOURCE, fallback=False)

        tapetide_attempted = False
        tapetide_results: list[CompanySearchResult] = []

        if (
            self._tapetide is not None
            and self._settings.tapetide_mcp_enabled
            and self._settings.tapetide_token_configured
        ):
            tapetide_attempted = True
            try:
                tapetide_results = await self._tapetide.search_stocks(cleaned, limit=capped_limit)
            except TapetideMcpServiceError as exc:
                logger.warning("Tapetide company search failed: %s", exc)

        if tapetide_results:
            return CompanySearchResponse(
                results=_dedupe_results(tapetide_results, cleaned)[:capped_limit],
                source=TAPETIDE_MCP_SOURCE,
                fallback=True,
            )

        yahoo_attempted = False
        if self._yahoo is not None:
            yahoo_attempted = True
            try:
                yahoo_results = await self._search_yahoo(cleaned, capped_limit)
                if yahoo_results:
                    return CompanySearchResponse(
                        results=yahoo_results,
                        source=YAHOO_SOURCE,
                        fallback=tapetide_attempted,
                    )
            except Exception as exc:
                logger.warning("Yahoo company search failed: %s", exc)

        if yahoo_attempted or tapetide_attempted:
            return CompanySearchResponse(
                results=[],
                source=YAHOO_SOURCE if yahoo_attempted else TAPETIDE_MCP_SOURCE,
                fallback=True,
            )

        return CompanySearchResponse(results=[], source=NSE_SOURCE, fallback=False)

    def _search_nse_master(self, query: str, limit: int) -> list[CompanySearchResult]:
        resolved = self._resolver.search(query, limit=limit)
        return [
            CompanySearchResult(
                symbol=item.symbol,
                exchange=item.exchange,
                company_name=item.company_name,
                sector=None,
                source=NSE_SOURCE,
            )
            for item in resolved
        ]

    async def _search_yahoo(self, query: str, limit: int) -> list[CompanySearchResult]:
        if self._yahoo is None:
            return []
        raw = await self._yahoo.search_companies(query, limit=limit)
        return [
            CompanySearchResult(
                symbol=item["symbol"],
                exchange=item.get("exchange", "NSE"),
                company_name=item["company_name"],
                sector=item.get("sector"),
                source=YAHOO_SOURCE,
            )
            for item in raw
        ]


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _dedupe_results(results: list[CompanySearchResult], query: str) -> list[CompanySearchResult]:
    normalized_query = _normalize(query)
    seen: set[str] = set()
    unique: list[CompanySearchResult] = []

    for item in results:
        key = item.symbol.upper()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return sorted(
        unique,
        key=lambda item: (
            -_match_score(normalized_query, item.symbol, item.company_name),
            len(item.symbol),
            item.company_name.lower(),
        ),
    )


def _match_score(normalized_query: str, ticker: str, name: str) -> int:
    score = 0
    ticker_norm = _normalize(ticker)
    name_norm = _normalize(name)

    if ticker_norm == normalized_query:
        score += 400
    elif ticker_norm.startswith(normalized_query):
        score += 300
    elif name_norm.startswith(normalized_query):
        score += 200
    elif normalized_query in name_norm:
        score += 100

    return score
