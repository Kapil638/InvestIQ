"""Tests for the curated large-cap seed candidates used by AdvisorRetrieval
when the user's profile requests large-cap/blue-chip stocks — added because
the existing fuzzy company-name search has no way to identify actual
large-cap companies and was surfacing obscure small-cap shell companies."""

import pytest

from app.data.large_cap_universe import LARGE_CAP_UNIVERSE
from app.providers.data_sources import CURATED_LARGE_CAP_SOURCE
from app.schemas.advisor import InvestorProfile
from app.services.advisor_retrieval import AdvisorRetrieval, _large_cap_seed_candidates


def test_large_cap_universe_entries_have_required_fields() -> None:
    assert len(LARGE_CAP_UNIVERSE) >= 50
    seen_symbols: set[str] = set()
    for entry in LARGE_CAP_UNIVERSE:
        assert entry["symbol"]
        assert entry["company_name"]
        assert entry["sector"]
        assert entry["symbol"] not in seen_symbols, f"duplicate symbol {entry['symbol']}"
        seen_symbols.add(entry["symbol"])


def test_large_cap_seed_candidates_respects_avoidances() -> None:
    candidates = _large_cap_seed_candidates(avoidances=["Reliance"])
    symbols = {c.symbol for c in candidates}
    assert "RELIANCE" not in symbols
    assert "TCS" in symbols  # unaffected candidate still present
    assert all(c.source == CURATED_LARGE_CAP_SOURCE for c in candidates)


@pytest.mark.asyncio
async def test_retrieve_with_fallback_seeds_large_cap_when_requested(monkeypatch) -> None:
    class _EmptySearchService:
        async def search(self, query, *, limit=10):
            from app.schemas.company_search import CompanySearchResponse

            return CompanySearchResponse(results=[], source="nse")

    retrieval = AdvisorRetrieval(
        search_service=_EmptySearchService(),
        tavily_api_key=None,
    )
    profile = InvestorProfile(market_cap_preference="large cap")

    results, providers = await retrieval.retrieve_with_fallback(
        profile, search_queries=[], theme_keywords=[], broad_market=True
    )

    assert len(results) > 0
    assert CURATED_LARGE_CAP_SOURCE in providers
    assert any(r.symbol == "RELIANCE" for r in results)


@pytest.mark.asyncio
async def test_retrieve_with_fallback_does_not_seed_without_large_cap_preference() -> None:
    class _EmptySearchService:
        async def search(self, query, *, limit=10):
            from app.schemas.company_search import CompanySearchResponse

            return CompanySearchResponse(results=[], source="nse")

    retrieval = AdvisorRetrieval(
        search_service=_EmptySearchService(),
        tavily_api_key=None,
    )
    profile = InvestorProfile()  # no market_cap_preference stated

    results, providers = await retrieval.retrieve_with_fallback(
        profile, search_queries=[], theme_keywords=[], broad_market=True
    )

    assert CURATED_LARGE_CAP_SOURCE not in providers
