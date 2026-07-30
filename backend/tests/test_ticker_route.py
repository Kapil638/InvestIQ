"""Tests for the public pre-login market ticker route."""

from datetime import datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_tapetide_service
from app.api.routes import ticker as ticker_module
from app.core.config import Settings
from app.main import create_app
from app.schemas.tapetide import TapetideQuoteResponse
from app.utils.exceptions import TapetideMcpNotEnabledError


@pytest.fixture(autouse=True)
def _reset_ticker_cache():
    ticker_module._cache = None
    yield
    ticker_module._cache = None


def _make_client(mock_service: AsyncMock, **settings_kwargs) -> TestClient:
    app = create_app(settings=Settings(app_env="test", debug=True, **settings_kwargs))
    app.dependency_overrides[get_tapetide_service] = lambda: mock_service
    return TestClient(app)


def _all_symbol_quotes() -> dict[str, TapetideQuoteResponse]:
    return {
        symbol: TapetideQuoteResponse(symbol=symbol, last_price=100.0, change_percent=1.0)
        for symbol, _ in ticker_module.TOP_NIFTY_SYMBOLS
    }


def test_ticker_route_is_not_gated() -> None:
    """The login page renders pre-session, so this route must stay open even
    when the owner-auth gate is configured - unlike every other market route."""
    mock_service = AsyncMock()
    mock_service.get_batch_quotes.return_value = _all_symbol_quotes()
    client = _make_client(mock_service, allowed_owner_emails="owner@example.com")

    response = client.get("/api/v1/ticker/nifty-top10")
    assert response.status_code == 200


def test_ticker_route_returns_all_symbols() -> None:
    mock_service = AsyncMock()
    mock_service.get_batch_quotes.return_value = _all_symbol_quotes()
    client = _make_client(mock_service)

    response = client.get("/api/v1/ticker/nifty-top10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == len(ticker_module.TOP_NIFTY_SYMBOLS)
    assert "market_open" in data
    assert "as_of" in data


def test_ticker_route_uses_one_batch_call() -> None:
    """Regression guard for the quota fix: must be a single get_batch_quotes
    call covering all symbols, not one get_quote call per symbol - Tapetide's
    free tier is a shared 50-calls/day budget across the whole app."""
    mock_service = AsyncMock()
    mock_service.get_batch_quotes.return_value = _all_symbol_quotes()
    client = _make_client(mock_service)

    client.get("/api/v1/ticker/nifty-top10")

    assert mock_service.get_batch_quotes.call_count == 1
    called_symbols = mock_service.get_batch_quotes.call_args.args[0]
    assert set(called_symbols) == {symbol for symbol, _ in ticker_module.TOP_NIFTY_SYMBOLS}


def test_ticker_route_skips_symbols_missing_from_batch_result() -> None:
    """A symbol absent from the batch response (Tapetide had no data and its
    own Yahoo fallback also came up empty) is skipped, not a crash."""
    mock_service = AsyncMock()
    quotes = _all_symbol_quotes()
    del quotes["TCS"]
    mock_service.get_batch_quotes.return_value = quotes
    client = _make_client(mock_service)

    response = client.get("/api/v1/ticker/nifty-top10")
    assert response.status_code == 200
    symbols = [item["symbol"] for item in response.json()["items"]]
    assert "TCS" not in symbols
    assert len(symbols) == len(ticker_module.TOP_NIFTY_SYMBOLS) - 1


def test_ticker_route_survives_batch_call_failure() -> None:
    """If the whole batch call throws (e.g. Tapetide disabled/unreachable and
    its own Yahoo fallback also failed), the endpoint still returns 200 with
    an empty item list instead of a 500."""
    mock_service = AsyncMock()
    mock_service.get_batch_quotes.side_effect = TapetideMcpNotEnabledError("disabled")
    client = _make_client(mock_service)

    response = client.get("/api/v1/ticker/nifty-top10")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_ticker_route_caches_response_briefly() -> None:
    mock_service = AsyncMock()
    mock_service.get_batch_quotes.return_value = _all_symbol_quotes()
    client = _make_client(mock_service)

    client.get("/api/v1/ticker/nifty-top10")
    client.get("/api/v1/ticker/nifty-top10")

    assert mock_service.get_batch_quotes.call_count == 1


@pytest.mark.parametrize(
    "iso, expected",
    [
        ("2026-07-22T11:00:00", True),  # Wednesday, mid-session
        ("2026-07-22T09:00:00", False),  # before open
        ("2026-07-22T16:00:00", False),  # after close
        ("2026-07-25T11:00:00", False),  # Saturday
        ("2026-07-26T11:00:00", False),  # Sunday
        ("2026-07-22T09:15:00", True),  # exactly at open
        ("2026-07-22T15:30:00", True),  # exactly at close
    ],
)
def test_is_nse_market_open(iso: str, expected: bool) -> None:
    now = datetime.fromisoformat(iso).replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    assert ticker_module._is_nse_market_open(now) is expected
