"""Tests for Zerodha OAuth and authenticated Kite Connect flows."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_kite_auth_service, get_kite_service
from app.core.config import Settings
from app.main import create_app
from app.providers.kite_mcp_provider import TRADING_TOOL_NAMES
from app.schemas.kite import KiteStatusResponse
from app.services.kite_auth_service import KiteAuthService
from app.services.kite_token_store import KiteSession, KiteTokenStore
from app.services.kite_service import KiteService


@pytest.fixture
def token_store() -> KiteTokenStore:
    store = KiteTokenStore()
    store.clear()
    return store


@pytest.fixture
def auth_settings() -> Settings:
    return Settings(
        app_env="test",
        debug=True,
        kite_mcp_enabled=True,
        kite_api_key="test_api_key",
        kite_api_secret="test_api_secret",
        kite_frontend_redirect_url="http://localhost:5173/portfolio",
    )


def test_login_redirects_to_zerodha(auth_settings: Settings, token_store: KiteTokenStore) -> None:
    app = create_app(settings=auth_settings)
    auth = KiteAuthService(auth_settings, token_store=token_store)
    app.dependency_overrides[get_kite_auth_service] = lambda: auth

    client = TestClient(app, follow_redirects=False)
    response = client.get(f"{auth_settings.api_prefix}/kite/login")

    assert response.status_code == 302
    assert "kite.zerodha.com/connect/login" in response.headers["location"]
    assert "api_key=test_api_key" in response.headers["location"]


@pytest.mark.asyncio
async def test_callback_exchanges_token_and_redirects(
    auth_settings: Settings, token_store: KiteTokenStore
) -> None:
    app = create_app(settings=auth_settings)
    auth = KiteAuthService(auth_settings, token_store=token_store)
    app.dependency_overrides[get_kite_auth_service] = lambda: auth

    session = KiteSession(
        access_token="access-token-123",
        user_id="AB1234",
        user_name="Kapil",
        broker="ZERODHA",
        login_time=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )

    async def _fake_exchange(_token: str) -> KiteSession:
        token_store.set_session(session)
        return session

    with patch.object(
        auth.connect_client, "exchange_request_token", AsyncMock(side_effect=_fake_exchange)
    ):
        client = TestClient(app, follow_redirects=False)
        response = client.get(
            f"{auth_settings.api_prefix}/kite/callback",
            params={"request_token": "req-token", "status": "success"},
        )

    assert response.status_code == 302
    assert "kite_connected=1" in response.headers["location"]
    assert token_store.is_authenticated()


def test_status_shows_authenticated_when_session_valid(
    auth_settings: Settings, token_store: KiteTokenStore
) -> None:
    token_store.set_session(
        KiteSession(
            access_token="token",
            user_id="AB1234",
            user_name="Kapil",
            broker="ZERODHA",
            login_time=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )
    )

    app = create_app(settings=auth_settings)
    mock_kite = MagicMock()
    mock_kite.get_status = AsyncMock(
        return_value=KiteStatusResponse(
            enabled=True,
            read_only=True,
            authenticated=True,
            connected=True,
            user_id="AB1234",
            broker="Zerodha",
            message="Connected to Zerodha as AB1234.",
        )
    )
    app.dependency_overrides[get_kite_service] = lambda: mock_kite

    client = TestClient(app)
    data = client.get(f"{auth_settings.api_prefix}/kite/status").json()

    assert data["authenticated"] is True
    assert data["connected"] is True
    assert data["user_id"] == "AB1234"
    assert data["broker"] == "Zerodha"


def test_status_unauthenticated_when_no_token(auth_settings: Settings) -> None:
    app = create_app(settings=auth_settings)
    client = TestClient(app)
    data = client.get(f"{auth_settings.api_prefix}/kite/status").json()

    assert data["enabled"] is True
    assert data["authenticated"] is False
    assert data["connected"] is False


def test_trading_tools_still_blocked(auth_settings: Settings) -> None:
    from app.providers.kite_mcp_provider import KiteMcpProvider

    provider = KiteMcpProvider(auth_settings)
    for tool in TRADING_TOOL_NAMES:
        assert provider.is_tool_allowed(tool) is False


@pytest.mark.asyncio
async def test_holdings_require_authentication(auth_settings: Settings) -> None:
    app = create_app(settings=auth_settings)
    service = KiteService(settings=auth_settings, auth_service=KiteAuthService(auth_settings))
    app.dependency_overrides[get_kite_service] = lambda: service

    from app.api.dependencies import get_portfolio_holdings_service
    from app.services.portfolio_holdings_service import PortfolioHoldingsService

    app.dependency_overrides[get_portfolio_holdings_service] = lambda: PortfolioHoldingsService(service)

    client = TestClient(app)
    data = client.get(f"{auth_settings.api_prefix}/kite/holdings").json()

    assert data["auth_required"] is True
    assert data["holdings"] == []
