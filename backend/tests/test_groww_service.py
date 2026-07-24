from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_groww_service
from app.core.config import Settings
from app.main import create_app
from app.schemas.groww import GrowwStatusResponse
from app.services.groww_service import (
    CREDENTIALS_MISSING_MESSAGE,
    DISABLED_MESSAGE,
    GrowwService,
)
from app.utils.exceptions import GrowwNotEnabledError, GrowwServiceError


@pytest.mark.asyncio
async def test_status_disabled() -> None:
    settings = Settings(app_env="test", debug=True, groww_enabled=False)
    service = GrowwService(settings=settings, client=MagicMock())

    result = await service.get_status()

    assert result.enabled is False
    assert result.message == DISABLED_MESSAGE


@pytest.mark.asyncio
async def test_status_enabled_missing_credentials() -> None:
    settings = Settings(
        app_env="test", debug=True, groww_enabled=True, groww_api_key=None, groww_api_secret=None
    )
    service = GrowwService(settings=settings, client=MagicMock())

    result = await service.get_status()

    assert result.enabled is True
    assert result.credentials_configured is False
    assert result.message == CREDENTIALS_MISSING_MESSAGE


@pytest.mark.asyncio
async def test_status_connected_reports_profile() -> None:
    settings = Settings(
        app_env="test",
        debug=True,
        groww_enabled=True,
        groww_api_key="key",
        groww_api_secret="secret",
    )
    mock_client = MagicMock()
    mock_client.get_profile = AsyncMock(return_value={"ucc": "ABC123"})
    service = GrowwService(settings=settings, client=mock_client)

    result = await service.get_status()

    assert result.connected is True
    assert "ABC123" in result.message


@pytest.mark.asyncio
async def test_status_client_failure_reported_not_raised() -> None:
    settings = Settings(
        app_env="test",
        debug=True,
        groww_enabled=True,
        groww_api_key="key",
        groww_api_secret="secret",
    )
    mock_client = MagicMock()
    mock_client.get_profile = AsyncMock(side_effect=GrowwServiceError("token rejected"))
    service = GrowwService(settings=settings, client=mock_client)

    result = await service.get_status()

    assert result.connected is False
    assert "token rejected" in result.message


@pytest.mark.asyncio
async def test_get_holdings_raises_when_disabled() -> None:
    settings = Settings(app_env="test", debug=True, groww_enabled=False)
    service = GrowwService(settings=settings, client=MagicMock())

    with pytest.raises(GrowwNotEnabledError):
        await service.get_holdings()


@pytest.mark.asyncio
async def test_get_holdings_enriches_with_yahoo_price() -> None:
    settings = Settings(
        app_env="test",
        debug=True,
        groww_enabled=True,
        groww_api_key="key",
        groww_api_secret="secret",
    )
    mock_client = MagicMock()
    mock_client.get_holdings = AsyncMock(
        return_value={
            "holdings": [
                {
                    "isin": "INE522F01014",
                    "trading_symbol": "COALINDIA",
                    "quantity": 100.0,
                    "average_price": 400.0,
                    "tradable_exchanges": ["NSE", "BSE"],
                }
            ]
        }
    )
    mock_yahoo = MagicMock()
    mock_yahoo.get_current_price = AsyncMock(return_value=450.0)

    service = GrowwService(settings=settings, client=mock_client, yahoo_provider=mock_yahoo)
    result = await service.get_holdings()

    assert len(result.holdings) == 1
    holding = result.holdings[0]
    assert holding.trading_symbol == "COALINDIA"
    assert holding.quantity == 100.0
    assert holding.average_price == 400.0
    assert holding.last_price == 450.0
    assert holding.pnl == pytest.approx(5000.0)


@pytest.mark.asyncio
async def test_get_holdings_survives_yahoo_failure() -> None:
    settings = Settings(
        app_env="test",
        debug=True,
        groww_enabled=True,
        groww_api_key="key",
        groww_api_secret="secret",
    )
    mock_client = MagicMock()
    mock_client.get_holdings = AsyncMock(
        return_value={
            "holdings": [
                {
                    "trading_symbol": "COALINDIA",
                    "quantity": 100.0,
                    "average_price": 400.0,
                    "tradable_exchanges": ["NSE"],
                }
            ]
        }
    )
    mock_yahoo = MagicMock()
    mock_yahoo.get_current_price = AsyncMock(side_effect=RuntimeError("Yahoo down"))

    service = GrowwService(settings=settings, client=mock_client, yahoo_provider=mock_yahoo)
    result = await service.get_holdings()

    assert len(result.holdings) == 1
    assert result.holdings[0].last_price is None
    assert result.holdings[0].pnl is None


def test_groww_status_route_disabled() -> None:
    settings = Settings(app_env="test", debug=True, groww_enabled=False)
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.get(f"{settings.api_prefix}/groww/status")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False


def test_groww_status_route_enabled_connected() -> None:
    settings = Settings(app_env="test", debug=True, groww_enabled=True)
    app = create_app(settings=settings)

    mock_service = AsyncMock()
    mock_service.get_status.return_value = GrowwStatusResponse(
        enabled=True,
        credentials_configured=True,
        connected=True,
        message="Connected to Groww as ABC123.",
    )
    app.dependency_overrides[get_groww_service] = lambda: mock_service

    client = TestClient(app)
    response = client.get(f"{settings.api_prefix}/groww/status")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True


def test_read_only_guarantee_no_trading_methods_referenced() -> None:
    """Regression guard: place_order/modify_order/cancel_order (and their smart-order
    GTT/OCO equivalents) must never be referenced anywhere in the Groww integration."""
    import pathlib

    backend_root = pathlib.Path(__file__).resolve().parent.parent
    # Match actual invocations only ("term(" or ".term") — not the explanatory
    # prose in these files' own docstrings, which names these methods on purpose.
    forbidden_calls = (
        "place_order(",
        "modify_order(",
        "cancel_order(",
        ".create_smart_order",
        ".modify_smart_order",
        ".cancel_smart_order",
    )
    for relative in (
        "app/providers/groww_client.py",
        "app/services/groww_service.py",
        "app/api/routes/groww.py",
    ):
        text = (backend_root / relative).read_text(encoding="utf-8")
        for term in forbidden_calls:
            assert term not in text, f"{relative} must never reference '{term}'"
