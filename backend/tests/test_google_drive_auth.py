"""Tests for Google Drive OAuth login, callback, and status flows."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_google_drive_auth_service
from app.core.config import Settings
from app.main import create_app
from app.services.google_drive_auth_service import GoogleDriveAuthService
from app.services.google_drive_token_store import GoogleDriveOAuthSession, GoogleDriveTokenStore


@pytest.fixture
def token_store(tmp_path) -> GoogleDriveTokenStore:
    store = GoogleDriveTokenStore(path=tmp_path / "google-drive-oauth-token.json")
    store.clear()
    return store


@pytest.fixture
def auth_settings() -> Settings:
    return Settings(
        app_env="test",
        debug=True,
        google_drive_enabled=True,
        google_drive_oauth_client_id="test_client_id",
        google_drive_oauth_client_secret="test_client_secret",
        google_drive_oauth_frontend_redirect_url="http://localhost:5173/reports",
    )


def test_login_redirects_to_google(
    auth_settings: Settings, token_store: GoogleDriveTokenStore
) -> None:
    app = create_app(settings=auth_settings)
    auth = GoogleDriveAuthService(auth_settings, token_store=token_store)
    app.dependency_overrides[get_google_drive_auth_service] = lambda: auth

    client = TestClient(app, follow_redirects=False)
    response = client.get(f"{auth_settings.api_prefix}/google-drive/login")

    assert response.status_code == 302
    location = response.headers["location"]
    assert "accounts.google.com/o/oauth2/v2/auth" in location
    assert "client_id=test_client_id" in location
    assert "access_type=offline" in location


@pytest.mark.asyncio
async def test_callback_exchanges_code_and_redirects(
    auth_settings: Settings, token_store: GoogleDriveTokenStore
) -> None:
    app = create_app(settings=auth_settings)
    auth = GoogleDriveAuthService(auth_settings, token_store=token_store)
    app.dependency_overrides[get_google_drive_auth_service] = lambda: auth

    with (
        patch.object(
            auth._client,
            "exchange_code",
            AsyncMock(
                return_value={
                    "access_token": "access-123",
                    "refresh_token": "refresh-123",
                    "expires_in": 3600,
                    "scope": "https://www.googleapis.com/auth/drive.file",
                }
            ),
        ),
        patch.object(auth._client, "fetch_user_email", AsyncMock(return_value="kapil@gmail.com")),
    ):
        client = TestClient(app, follow_redirects=False)
        # get_login_url() sets the process-wide pending state that /callback checks
        auth.get_login_url()
        response = client.get(
            f"{auth_settings.api_prefix}/google-drive/callback",
            params={"code": "auth-code", "state": _current_pending_state()},
        )

    assert response.status_code == 302
    assert "drive_connected=1" in response.headers["location"]
    assert token_store.is_authenticated()
    session = token_store.get_session()
    assert session is not None
    assert session.user_email == "kapil@gmail.com"


@pytest.mark.asyncio
async def test_callback_redirects_with_error_on_missing_code(
    auth_settings: Settings, token_store: GoogleDriveTokenStore
) -> None:
    app = create_app(settings=auth_settings)
    auth = GoogleDriveAuthService(auth_settings, token_store=token_store)
    app.dependency_overrides[get_google_drive_auth_service] = lambda: auth

    client = TestClient(app, follow_redirects=False)
    response = client.get(f"{auth_settings.api_prefix}/google-drive/callback")

    assert response.status_code == 302
    assert "drive_error=1" in response.headers["location"]
    assert not token_store.is_authenticated()


def test_status_unauthenticated_when_no_token(
    auth_settings: Settings, token_store: GoogleDriveTokenStore
) -> None:
    app = create_app(settings=auth_settings)
    auth = GoogleDriveAuthService(auth_settings, token_store=token_store)
    app.dependency_overrides[get_google_drive_auth_service] = lambda: auth

    client = TestClient(app)
    data = client.get(f"{auth_settings.api_prefix}/google-drive/status").json()

    assert data["enabled"] is True
    assert data["oauth_configured"] is True
    assert data["authenticated"] is False
    assert data["connected"] is False


def test_status_authenticated_when_session_present(
    auth_settings: Settings, token_store: GoogleDriveTokenStore
) -> None:
    token_store.set_session(
        GoogleDriveOAuthSession(
            access_token="access-123",
            refresh_token="refresh-123",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            scopes=["https://www.googleapis.com/auth/drive.file"],
            expiry="2030-01-01T00:00:00+00:00",
            user_email="kapil@gmail.com",
        )
    )

    app = create_app(settings=auth_settings)
    auth = GoogleDriveAuthService(auth_settings, token_store=token_store)
    app.dependency_overrides[get_google_drive_auth_service] = lambda: auth

    client = TestClient(app)
    data = client.get(f"{auth_settings.api_prefix}/google-drive/status").json()

    assert data["authenticated"] is True
    assert data["connected"] is True
    assert data["user_email"] == "kapil@gmail.com"


def test_logout_clears_session(
    auth_settings: Settings, token_store: GoogleDriveTokenStore
) -> None:
    token_store.set_session(
        GoogleDriveOAuthSession(
            access_token="access-123",
            refresh_token="refresh-123",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            scopes=["https://www.googleapis.com/auth/drive.file"],
            expiry="2030-01-01T00:00:00+00:00",
        )
    )

    app = create_app(settings=auth_settings)
    auth = GoogleDriveAuthService(auth_settings, token_store=token_store)
    app.dependency_overrides[get_google_drive_auth_service] = lambda: auth

    client = TestClient(app)
    response = client.post(f"{auth_settings.api_prefix}/google-drive/logout")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert not token_store.is_authenticated()


def _current_pending_state() -> str:
    from app.services import google_drive_auth_service as mod

    assert mod._pending_state is not None
    return mod._pending_state
