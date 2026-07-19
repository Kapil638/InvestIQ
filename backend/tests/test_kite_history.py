from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_financial_data_service, get_kite_service
from app.core.config import Settings
from app.main import create_app
from app.providers.yahoo_finance_provider import YahooFinanceProvider
from app.schemas.financial import HistoricalPricePoint
from app.schemas.history import HistoricalCandle
from app.schemas.kite import KiteHistoryResponse
from app.services.financial_data_service import FinancialDataService
from app.services.kite_service import KiteService, YAHOO_SOURCE
from app.utils.history_timeframe import resolve_timeframe, validate_interval


@pytest.fixture
def settings() -> Settings:
    return Settings(app_env="test", debug=True, kite_mcp_enabled=True, yfinance_enabled=True)


def _sample_candles() -> list[HistoricalPricePoint]:
    return [
        HistoricalPricePoint(
            date="2025-01-02",
            open=100.0,
            high=105.0,
            low=99.0,
            close=104.0,
            volume=120000,
        ),
        HistoricalPricePoint(
            date="2025-01-03",
            open=104.0,
            high=106.0,
            low=103.0,
            close=105.5,
            volume=98000,
        ),
    ]


def test_validate_interval_accepts_supported_values() -> None:
    assert validate_interval("day") == "day"
    assert validate_interval("5minute") == "5minute"


def test_validate_interval_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Invalid interval"):
        validate_interval("hour")


def test_resolve_timeframe_1y_uses_daily_candles() -> None:
    fixed = datetime(2025, 6, 15, tzinfo=UTC)
    interval, from_date, to_date = resolve_timeframe("1Y", now=fixed)

    assert interval == "day"
    assert to_date == "2025-06-15"
    assert from_date == "2024-06-15"


def test_resolve_timeframe_1d_uses_intraday() -> None:
    fixed = datetime(2025, 6, 15, tzinfo=UTC)
    interval, from_date, to_date = resolve_timeframe("1D", now=fixed)

    assert interval == "5minute"
    assert to_date == "2025-06-15"
    assert from_date == "2025-06-14"


@pytest.mark.asyncio
async def test_financial_service_price_history_via_kite(settings: Settings) -> None:
    mock_kite = MagicMock()
    mock_kite.get_history = AsyncMock(
        return_value=KiteHistoryResponse(
            symbol="INFY",
            kite_symbol="NSE:INFY",
            interval="day",
            candles=_sample_candles(),
            source="Kite Connect",
        )
    )

    mock_provider = MagicMock()
    service = FinancialDataService(provider=mock_provider, kite_service=mock_kite)
    candles = await service.get_price_history("INFY", interval="day", from_date="2025-01-01")

    assert len(candles) == 2
    assert isinstance(candles[0], HistoricalCandle)
    assert candles[0].timestamp == "2025-01-02"
    assert candles[0].close == 104.0
    mock_kite.get_history.assert_awaited_once()


@pytest.mark.asyncio
async def test_financial_service_yahoo_fallback_when_no_kite(settings: Settings) -> None:
    mock_provider = MagicMock()
    mock_provider.get_historical_candles = AsyncMock(return_value=_sample_candles())

    service = FinancialDataService(provider=mock_provider, kite_service=None)
    candles = await service.get_price_history(
        "INFY", interval="day", from_date="2025-01-01", to_date="2025-01-10"
    )

    assert len(candles) == 2
    assert candles[1].volume == 98000
    mock_provider.get_historical_candles.assert_awaited_once()


@pytest.mark.asyncio
async def test_kite_service_history_yahoo_fallback(settings: Settings) -> None:
    mock_provider = MagicMock()
    mock_provider.call_tool = AsyncMock(side_effect=RuntimeError("kite unavailable"))
    mock_yahoo = MagicMock()
    mock_yahoo.get_historical_candles = AsyncMock(return_value=_sample_candles())

    service = KiteService(settings=settings, provider=mock_provider, yahoo_provider=mock_yahoo)
    result = await service.get_history("INFY", interval="day", from_date="2025-01-01")

    assert result.source == YAHOO_SOURCE
    assert len(result.candles) == 2
    mock_yahoo.get_historical_candles.assert_awaited_once()


def test_history_endpoint_returns_candles(settings: Settings) -> None:
    app = create_app(settings=settings)

    mock_financial = MagicMock()
    mock_financial.get_price_history = AsyncMock(
        return_value=[
            HistoricalCandle(
                timestamp="2025-01-02T09:15:00",
                open=100.0,
                high=105.0,
                low=99.0,
                close=104.0,
                volume=235000,
            )
        ]
    )
    app.dependency_overrides[get_financial_data_service] = lambda: mock_financial

    client = TestClient(app)
    response = client.get(
        f"{settings.api_prefix}/kite/history/INFY",
        params={"interval": "day", "from": "2025-01-01", "to": "2025-01-10"},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["timestamp"] == "2025-01-02T09:15:00"
    assert data[0]["volume"] == 235000
    mock_financial.get_price_history.assert_awaited_once()


def test_history_endpoint_empty_dataset(settings: Settings) -> None:
    app = create_app(settings=settings)

    mock_financial = MagicMock()
    mock_financial.get_price_history = AsyncMock(return_value=[])
    app.dependency_overrides[get_financial_data_service] = lambda: mock_financial

    client = TestClient(app)
    response = client.get(f"{settings.api_prefix}/kite/history/INFY", params={"interval": "day"})

    assert response.status_code == 200
    assert response.json() == []


def test_history_endpoint_invalid_interval(settings: Settings) -> None:
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.get(
        f"{settings.api_prefix}/kite/history/INFY",
        params={"interval": "hour"},
    )

    assert response.status_code == 422


def test_history_endpoint_works_when_kite_disabled(settings: Settings) -> None:
    disabled_settings = Settings(
        app_env="test",
        debug=True,
        kite_mcp_enabled=False,
        yfinance_enabled=True,
    )
    app = create_app(settings=disabled_settings)

    mock_financial = MagicMock()
    mock_financial.get_price_history = AsyncMock(
        return_value=[
            HistoricalCandle(
                timestamp="2025-01-02",
                open=100.0,
                high=105.0,
                low=99.0,
                close=104.0,
                volume=1000,
            )
        ]
    )
    app.dependency_overrides[get_financial_data_service] = lambda: mock_financial

    client = TestClient(app)
    response = client.get(f"{disabled_settings.api_prefix}/kite/history/INFY")

    assert response.status_code == 200
    assert len(response.json()) == 1
