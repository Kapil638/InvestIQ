"""Candidate retrieval for advisor – provider search only, no hardcoded theme universes."""

from __future__ import annotations

import asyncio

from app.data.large_cap_universe import LARGE_CAP_UNIVERSE
from app.providers.data_sources import CURATED_LARGE_CAP_SOURCE
from app.schemas.advisor import InvestorProfile, RawCandidate, ThemeIntent
from app.schemas.company_search import CompanySearchResult
from app.services.advisor_utils import as_str_list, bare_symbol, candidate_blob, market_cap_tier_preference
from app.services.company_search_service import CompanySearchService
from app.services.symbol_resolver_service import SymbolResolverService, get_symbol_resolver_service
from app.services.tavily_client import TavilyClient
from app.utils.logging import get_logger

logger = get_logger(__name__)

MAX_RAW_CANDIDATES = 30
MAX_SEARCH_CALLS = 10


class AdvisorRetrieval:
    def __init__(
        self,
        search_service: CompanySearchService,
        tavily_api_key: str | None,
        symbol_resolver: SymbolResolverService | None = None,
    ) -> None:
        self._search = search_service
        self._tavily_key = tavily_api_key
        self._resolver = symbol_resolver or get_symbol_resolver_service()

    async def retrieve(
        self,
        profile: InvestorProfile,
        search_queries: list[str],
        theme_keywords: list[str],
    ) -> list[RawCandidate]:
        seen: set[str] = set()
        results: list[RawCandidate] = []

        def add_item(item: CompanySearchResult) -> None:
            sym = bare_symbol(item.symbol)
            if sym in seen:
                return
            if _matches_avoidances(item, profile.avoidances):
                return
            seen.add(sym)
            results.append(
                RawCandidate(
                    symbol=sym,
                    company_name=item.company_name,
                    exchange=item.exchange or "NSE",
                    sector=item.sector,
                    source=item.source,
                )
            )

        queries = _unique_queries(search_queries, theme_keywords)[:MAX_SEARCH_CALLS]
        for query in queries:
            try:
                response = await self._search.search(query, limit=10)
                for item in response.results:
                    add_item(item)
                    if len(results) >= MAX_RAW_CANDIDATES:
                        break
            except Exception as exc:
                logger.warning("Advisor retrieval search failed for %r: %s", query, exc)
            if len(results) >= MAX_RAW_CANDIDATES:
                break

        if len(results) < 8:
            for resolved in _keyword_master_matches(
                self._resolver,
                theme_keywords,
                profile.avoidances,
            ):
                if resolved.symbol in seen:
                    continue
                seen.add(resolved.symbol)
                results.append(
                    RawCandidate(
                        symbol=resolved.symbol,
                        company_name=resolved.company_name,
                        exchange=resolved.exchange,
                        sector=None,
                        source=resolved.source,
                    )
                )
                if len(results) >= MAX_RAW_CANDIDATES:
                    break

        if len(results) < 5 and self._tavily_key:
            tavily_names = await self._tavily_discovery(queries[:3])
            for name in tavily_names:
                try:
                    response = await self._search.search(name, limit=3)
                    for item in response.results:
                        add_item(item)
                except Exception:
                    continue
                if len(results) >= MAX_RAW_CANDIDATES:
                    break

        results.sort(key=lambda c: (0 if c.exchange.upper() == "NSE" else 1, c.symbol))
        logger.info(
            "Advisor retrieval: queries=%d raw_candidates=%d",
            len(queries),
            len(results),
        )
        return results[:MAX_RAW_CANDIDATES]

    async def retrieve_with_fallback(
        self,
        profile: InvestorProfile,
        search_queries: list[str],
        theme_keywords: list[str],
        *,
        broad_market: bool = False,
    ) -> tuple[list[RawCandidate], list[str]]:
        providers: set[str] = set()
        results = await self.retrieve(profile, search_queries, theme_keywords)
        for r in results:
            providers.add(r.source)

        # Scoped exception to "provider search only": fuzzy company-NAME text
        # search (both the master index and its downstream fallbacks) cannot
        # identify actual large-cap companies — it was surfacing obscure
        # small-cap shell companies whose legal names happen to contain
        # generic words like "Investment". "Large cap" is a well-defined,
        # slow-changing category, unlike subjective themes, so a small curated
        # seed list is used here — every entry still goes through the same
        # real-data enrichment and market-cap validation as any other
        # candidate, so a stale/wrong entry gets filtered out downstream.
        if market_cap_tier_preference(profile.market_cap_preference) == "large":
            seen = {r.symbol for r in results}
            for entry in _large_cap_seed_candidates(profile.avoidances):
                if entry.symbol in seen:
                    continue
                seen.add(entry.symbol)
                results.append(entry)
                providers.add(entry.source)
                if len(results) >= MAX_RAW_CANDIDATES:
                    break

        if len(results) < 5:
            relaxed_queries = (
                ["large cap NSE India", "quality indian stocks", "blue chip india"]
                if broad_market
                else (search_queries or ["india stock NSE"])
            )
            seen = {r.symbol for r in results}
            for query in relaxed_queries:
                try:
                    response = await self._search.search(query, limit=12)
                    for item in response.results:
                        sym = bare_symbol(item.symbol)
                        if sym in seen:
                            continue
                        seen.add(sym)
                        results.append(
                            RawCandidate(
                                symbol=sym,
                                company_name=item.company_name,
                                exchange=item.exchange or "NSE",
                                sector=item.sector,
                                source=item.source,
                            )
                        )
                        providers.add(item.source)
                except Exception as exc:
                    logger.debug("Advisor fallback search failed: %s", exc)
                if len(results) >= MAX_RAW_CANDIDATES:
                    break

        if len(results) < 5:
            seen = {r.symbol for r in results}
            for resolved in self._resolver.keyword_matches(
                theme_keywords or ["large cap", "quality"],
                limit_per_keyword=8,
            ):
                if resolved.symbol in seen:
                    continue
                seen.add(resolved.symbol)
                results.append(
                    RawCandidate(
                        symbol=resolved.symbol,
                        company_name=resolved.company_name,
                        exchange=resolved.exchange,
                        sector=None,
                        source=resolved.source,
                    )
                )
                providers.add(resolved.source)
                if len(results) >= MAX_RAW_CANDIDATES:
                    break

        results.sort(key=lambda c: (0 if c.exchange.upper() == "NSE" else 1, c.symbol))
        return results[:MAX_RAW_CANDIDATES], sorted(providers)

    async def _tavily_discovery(self, queries: list[str]) -> list[str]:
        if not self._tavily_key:
            return []
        client = TavilyClient(api_key=self._tavily_key)
        names: list[str] = []
        try:
            for q in queries:
                full_q = f"India NSE BSE listed stocks {q}"
                try:
                    hits = await client.search(full_q, max_results=3)
                except Exception as exc:
                    logger.debug("Tavily discovery skipped: %s", exc)
                    continue
                for hit in hits:
                    title = str(hit.get("title") or "")
                    if title and len(title) > 3:
                        names.append(title[:80])
        finally:
            await client.close()
        return names[:6]


def _unique_queries(search_queries: list[str], theme_keywords: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for q in search_queries + [f"{k} india stock" for k in theme_keywords[:8]]:
        key = q.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(q.strip())
    return out


def _keyword_master_matches(
    resolver: SymbolResolverService,
    keywords: list[str],
    avoidances: list[str],
) -> list:
    if not keywords:
        return []
    matched = []
    for resolved in resolver.keyword_matches(keywords, limit_per_keyword=5):
        blob = candidate_blob(resolved.company_name, resolved.symbol)
        if avoidances and any(a.lower() in blob for a in avoidances):
            continue
        matched.append(resolved)
    return matched


def _matches_avoidances(item: CompanySearchResult, avoidances: list[str]) -> bool:
    if not avoidances:
        return False
    blob = candidate_blob(item.company_name, item.symbol, item.sector)
    return any(a.lower() in blob for a in avoidances)


def _large_cap_seed_candidates(avoidances: list[str]) -> list[RawCandidate]:
    candidates: list[RawCandidate] = []
    for entry in LARGE_CAP_UNIVERSE:
        blob = candidate_blob(entry["company_name"], entry["symbol"], entry["sector"])
        if avoidances and any(a.lower() in blob for a in avoidances):
            continue
        candidates.append(
            RawCandidate(
                symbol=entry["symbol"],
                company_name=entry["company_name"],
                exchange="NSE",
                sector=entry["sector"],
                source=CURATED_LARGE_CAP_SOURCE,
            )
        )
    return candidates
