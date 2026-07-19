import pytest

from app.providers.ticker import normalize_indian_ticker, validate_ticker_format
from app.providers.yahoo_finance_provider import (
    YahooFinanceProvider,
    _fetch_info_sync,
    _is_empty_info,
    _map_profile,
)
from app.utils.exceptions import TickerNotFoundError
from tests.fixtures.financial_data import SAMPLE_YAHOO_INFO


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("INFY", "INFY.NS"),
        ("RELIANCE", "RELIANCE.NS"),
        ("TCS", "TCS.NS"),
        ("HDFCBANK", "HDFCBANK.NS"),
        ("ICICIBANK", "ICICIBANK.NS"),
        ("SBIN", "SBIN.NS"),
        ("INFY.NS", "INFY.NS"),
        ("INFY.BO", "INFY.BO"),
    ],
)
def test_normalize_indian_tickers(raw: str, expected: str) -> None:
    assert normalize_indian_ticker(raw) == expected


def test_validate_ticker_format_rejects_empty() -> None:
    with pytest.raises(ValueError, match="required"):
        validate_ticker_format("")


def test_is_empty_info_detects_missing_data() -> None:
    assert _is_empty_info({}) is True
    assert _is_empty_info(SAMPLE_YAHOO_INFO) is False


def test_map_profile_from_yahoo_info() -> None:
    profile = _map_profile("INFY.NS", SAMPLE_YAHOO_INFO)

    assert profile.symbol == "INFY.NS"
    assert profile.company_name == "Infosys Limited"
    assert profile.currency == "INR"
    assert profile.market_cap == 700000000000


def test_fetch_info_sync_raises_for_invalid_ticker(monkeypatch) -> None:
    class FakeTicker:
        @property
        def info(self):
            return {}

    monkeypatch.setattr(
        "app.providers.yahoo_finance_provider.yf.Ticker",
        lambda _symbol: FakeTicker(),
    )

    with pytest.raises(TickerNotFoundError):
        _fetch_info_sync("INVALID.NS")


@pytest.mark.asyncio
async def test_provider_get_company_profile_calls_internal_runner(monkeypatch) -> None:
    from unittest.mock import AsyncMock

    provider = YahooFinanceProvider()
    mock_call = AsyncMock(return_value=SAMPLE_YAHOO_INFO)
    monkeypatch.setattr(provider, "_call", mock_call)

    profile = await provider.get_company_profile("INFY.NS")

    mock_call.assert_awaited_once()
    assert profile.company_name == "Infosys Limited"
