"""Central symbol resolution layer backed by local company master."""

from __future__ import annotations

import threading

from app.providers.data_sources import NSE_SOURCE
from app.providers.kite_symbols import to_kite_symbol
from app.providers.ticker import normalize_indian_ticker
from app.schemas.symbol import ResolvedSymbol
from app.services.advisor_utils import bare_symbol
from app.services.company_master_service import (
    CompanyMasterEntry,
    CompanyMasterService,
    get_company_master_service,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _entry_to_resolved(entry: CompanyMasterEntry) -> ResolvedSymbol:
    source_slug = entry.source.lower() if entry.source else NSE_SOURCE
    if source_slug == "nse":
        source_slug = NSE_SOURCE
    return ResolvedSymbol(
        symbol=entry.symbol,
        company_name=entry.company_name,
        exchange=entry.exchange or "NSE",
        isin=entry.isin,
        series=entry.series,
        source=source_slug,
    )


class SymbolResolverService:
    """Resolve user queries and bare symbols to canonical master entries."""

    def __init__(self, master_service: CompanyMasterService | None = None) -> None:
        self._master = master_service or get_company_master_service()

    def ensure_loaded(self) -> None:
        self._master.ensure_loaded()

    def search(self, query: str, *, limit: int = 15) -> list[ResolvedSymbol]:
        """Fuzzy search for autocomplete and discovery."""
        return [_entry_to_resolved(entry) for entry in self._master.search(query, limit=limit)]

    def resolve_one(self, query: str) -> ResolvedSymbol | None:
        """Return the best master match for a free-text query."""
        matches = self.search(query, limit=1)
        return matches[0] if matches else None

    def resolve_bare(self, symbol: str, exchange: str | None = None) -> ResolvedSymbol | None:
        """Exact lookup by bare ticker (and optional exchange)."""
        entry = self._master.lookup_by_symbol(symbol, exchange=exchange)
        return _entry_to_resolved(entry) if entry else None

    def resolve_query(self, query: str) -> ResolvedSymbol | None:
        """
        Resolve a query that may be a bare ticker, Yahoo ticker, or company name.
        Tries exact symbol first, then fuzzy search.
        """
        cleaned = query.strip()
        if not cleaned:
            return None

        bare = bare_symbol(cleaned)
        exact = self.resolve_bare(bare)
        if exact:
            return exact

        if len(cleaned) >= 2:
            return self.resolve_one(cleaned)
        return None

    def keyword_matches(self, keywords: list[str], *, limit_per_keyword: int = 5) -> list[ResolvedSymbol]:
        """Theme/keyword discovery for advisor retrieval fallbacks."""
        seen: set[str] = set()
        results: list[ResolvedSymbol] = []
        for keyword in keywords:
            key = keyword.strip().lower()
            if not key:
                continue
            for resolved in self.search(keyword, limit=limit_per_keyword):
                if resolved.symbol in seen:
                    continue
                seen.add(resolved.symbol)
                results.append(resolved)
        return results

    def to_yahoo_ticker(self, resolved: ResolvedSymbol) -> str:
        return normalize_indian_ticker(resolved.symbol)

    def to_kite_symbol(self, resolved: ResolvedSymbol) -> str:
        return to_kite_symbol(resolved.symbol, exchange=resolved.exchange)


_resolver_service: SymbolResolverService | None = None
_resolver_lock = threading.Lock()


def get_symbol_resolver_service() -> SymbolResolverService:
    global _resolver_service
    if _resolver_service is None:
        with _resolver_lock:
            if _resolver_service is None:
                _resolver_service = SymbolResolverService()
    return _resolver_service


def reset_symbol_resolver_service_for_tests() -> None:
    global _resolver_service
    with _resolver_lock:
        _resolver_service = None
