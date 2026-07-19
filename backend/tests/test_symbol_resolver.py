"""Tests for central symbol resolver layer."""

import pytest

from app.providers.data_sources import NSE_SOURCE
from app.providers.ticker import normalize_indian_ticker
from app.services.company_master_service import reset_company_master_service_for_tests
from app.services.symbol_resolver_service import (
    SymbolResolverService,
    get_symbol_resolver_service,
    reset_symbol_resolver_service_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singletons() -> None:
    reset_symbol_resolver_service_for_tests()
    reset_company_master_service_for_tests()
    yield
    reset_symbol_resolver_service_for_tests()
    reset_company_master_service_for_tests()


@pytest.fixture
def resolver() -> SymbolResolverService:
    service = get_symbol_resolver_service()
    service.ensure_loaded()
    return service


def test_resolve_bare_infy(resolver: SymbolResolverService) -> None:
    resolved = resolver.resolve_bare("INFY")
    assert resolved is not None
    assert resolved.symbol == "INFY"
    assert "infosys" in resolved.company_name.lower()
    assert resolved.exchange == "NSE"
    assert resolved.source == NSE_SOURCE


def test_resolve_query_infosys_name(resolver: SymbolResolverService) -> None:
    resolved = resolver.resolve_one("infosys")
    assert resolved is not None
    assert resolved.symbol == "INFY"


def test_search_inf_returns_infosys(resolver: SymbolResolverService) -> None:
    results = resolver.search("inf", limit=5)
    assert results[0].symbol == "INFY"


def test_to_yahoo_ticker(resolver: SymbolResolverService) -> None:
    resolved = resolver.resolve_bare("INFY")
    assert resolved is not None
    assert resolver.to_yahoo_ticker(resolved) == normalize_indian_ticker("INFY")


def test_keyword_matches_defence(resolver: SymbolResolverService) -> None:
    matches = resolver.keyword_matches(["defence"], limit_per_keyword=5)
    assert matches
    assert all(item.symbol for item in matches)
