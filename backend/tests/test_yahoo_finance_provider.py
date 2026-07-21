"""Tests for YahooFinanceProvider._call's transient-failure retry behavior."""

from unittest.mock import AsyncMock, patch

import pytest

from app.providers.yahoo_finance_provider import YahooFinanceProvider
from app.utils.exceptions import ExternalServiceError, TickerNotFoundError


@pytest.fixture
def provider() -> YahooFinanceProvider:
    return YahooFinanceProvider()


@pytest.mark.asyncio
async def test_call_retries_after_transient_failure_then_succeeds(
    provider: YahooFinanceProvider,
) -> None:
    calls = {"count": 0}

    def flaky_fn(ticker: str) -> str:
        calls["count"] += 1
        if calls["count"] < 2:
            raise ConnectionError("Could not resolve host: query2.finance.yahoo.com")
        return "ok"

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await provider._call("get_company_profile", "BPCL.NS", flaky_fn)

    assert result == "ok"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_call_raises_external_service_error_after_exhausting_retries(
    provider: YahooFinanceProvider,
) -> None:
    calls = {"count": 0}

    def always_fails(ticker: str) -> str:
        calls["count"] += 1
        raise ConnectionError("Could not resolve host")

    with patch("asyncio.sleep", new=AsyncMock()):
        with pytest.raises(ExternalServiceError) as exc_info:
            await provider._call("get_company_profile", "BPCL.NS", always_fails)

    assert calls["count"] == 3  # 1 initial attempt + 2 retries
    assert "get_company_profile" in str(exc_info.value)
    assert "BPCL.NS" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, ConnectionError)


@pytest.mark.asyncio
async def test_call_does_not_retry_ticker_not_found(provider: YahooFinanceProvider) -> None:
    calls = {"count": 0}

    def not_found(ticker: str) -> str:
        calls["count"] += 1
        raise TickerNotFoundError(f"No data for {ticker}")

    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        with pytest.raises(TickerNotFoundError):
            await provider._call("get_company_profile", "NOTREAL.NS", not_found)

    assert calls["count"] == 1
    mock_sleep.assert_not_awaited()
