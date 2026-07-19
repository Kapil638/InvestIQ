"""Tests for NSE company master search service."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.company_master_service import (
    CompanyMasterService,
    normalize_query,
    reset_company_master_service_for_tests,
)


@pytest.fixture(autouse=True)
def reset_master_singleton() -> None:
    reset_company_master_service_for_tests()
    yield
    reset_company_master_service_for_tests()


@pytest.fixture
def master_service() -> CompanyMasterService:
    service = CompanyMasterService()
    service.ensure_loaded()
    return service


def test_search_inf_returns_infosys(master_service: CompanyMasterService) -> None:
    results = master_service.search("inf", limit=15)
    symbols = [item.symbol for item in results]
    assert "INFY" in symbols
    assert results[0].symbol == "INFY"


def test_search_infosys_returns_infosys(master_service: CompanyMasterService) -> None:
    results = master_service.search("infosys", limit=15)
    assert any(item.symbol == "INFY" for item in results)


def test_search_reli_returns_reliance_companies(master_service: CompanyMasterService) -> None:
    results = master_service.search("reli", limit=15)
    names = " ".join(item.company_name.lower() for item in results)
    assert "reliance" in names


def test_search_hdfc_returns_hdfc_companies(master_service: CompanyMasterService) -> None:
    results = master_service.search("hdfc", limit=15)
    assert any("hdfc" in item.company_name.lower() or item.symbol.startswith("HDFC") for item in results)


def test_search_tat_returns_tata_companies(master_service: CompanyMasterService) -> None:
    results = master_service.search("tat", limit=15)
    assert any("tata" in item.company_name.lower() or item.symbol.startswith("TATA") for item in results)


def test_search_is_case_insensitive(master_service: CompanyMasterService) -> None:
    lower = master_service.search("infy", limit=5)
    upper = master_service.search("INFY", limit=5)
    assert [item.symbol for item in lower] == [item.symbol for item in upper]


def test_search_ignores_ltd_limited(master_service: CompanyMasterService) -> None:
    with_ltd = master_service.search("infosys limited", limit=5)
    without = master_service.search("infosys", limit=5)
    assert [item.symbol for item in with_ltd] == [item.symbol for item in without]


def test_normalize_query_strips_ltd() -> None:
    assert normalize_query("Infosys Limited") == normalize_query("Infosys")


def test_json_loads_only_once() -> None:
    service = CompanyMasterService()
    data_path = Path(__file__).resolve().parents[1] / "app" / "data" / "company_master.json"
    service._data_path = data_path

    with patch.object(service, "_read_entries", wraps=service._read_entries) as mock_read:
        service.ensure_loaded()
        service.search("inf")
        service.search("hdfc")
        service.search("tat")
        assert service.load_count == 1
        mock_read.assert_called_once()


def test_search_returns_max_15(master_service: CompanyMasterService) -> None:
    results = master_service.search("a", limit=15)
    assert len(results) <= 15
