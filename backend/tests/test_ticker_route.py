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
from app.utils.exceptions import TapetideMcpServiceError


@pytest.fixture(autouse=True)
def _reset_ticker_cache():
    ticker_module._cache = None
    yield
    ticker_module._cache = None


def _make_client(mock_service: AsyncMock, **settings_kwargs) -> TestClient:
    app = create_app(settings=Settings(app_env="test", debug=True, **settings_kwargs))
    app.dependency_overrides[get_tapetide_service] = lambda: mock_service
    return TestClient(app)


def test_ticker_route_is_not_gated() -> None:
    """The login page renders pre-session, so this route must stay open even
    when the owner-auth gate is configured - unlike every other market route."""
    mock_service = AsyncMock()
    mock_service.get_quote.return_value = TapetideQuoteResponse(
        symbol="RELIANCE", last_price=2945.6, change_percent=0.82
    )
    client = _make_client(mock_service, allowed_owner_emails="owner@example.com")

    response = client.get("/api/v1/ticker/nifty-top10")
    assert response.status_code == 200


def test_ticker_route_returns_all_symbols() -> None:
    mock_service = AsyncMock()
    mock_service.get_quote.return_value = TapetideQuoteResponse(
        symbol="RELIANCE", last_price=2945.6, change_percent=0.82
    )
    client = _make_client(mock_service)

    response = client.get("/api/v1/ticker/nifty-top10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == len(ticker_module.TOP_NIFTY_SYMBOLS)
    assert "market_open" in data
    assert "as_of" in data


def test_ticker_route_skips_symbols_with_failed_quotes() -> None:
    mock_service = AsyncMock()

    async def flaky_get_quote(symbol, **kwargs):
        if symbol == "TCS":
            raise TapetideMcpServiceError("boom")
        return TapetideQuoteResponse(symbol=symbol, last_price=100.0, change_percent=1.0)

    mock_service.get_quote.side_effect = flaky_get_quote
    client = _make_client(mock_service)

    response = client.get("/api/v1/ticker/nifty-top10")
    assert response.status_code == 200
    symbols = [item["symbol"] for item in response.json()["items"]]
    assert "TCS" not in symbols
    assert len(symbols) == len(ticker_module.TOP_NIFTY_SYMBOLS) - 1


def test_ticker_route_caches_response_briefly() -> None:
    mock_service = AsyncMock()
    mock_service.get_quote.return_value = TapetideQuoteResponse(
        symbol="RELIANCE", last_price=2945.6, change_percent=0.82
    )
    client = _make_client(mock_service)

    client.get("/api/v1/ticker/nifty-top10")
    client.get("/api/v1/ticker/nifty-top10")

    assert mock_service.get_quote.call_count == len(ticker_module.TOP_NIFTY_SYMBOLS)


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
