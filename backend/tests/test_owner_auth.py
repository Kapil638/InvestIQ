"""Tests for the owner authentication gate (Google Sign-In + session cookie)."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_owner_auth_service, get_user_repository
from app.core.config import Settings
from app.main import create_app
from app.services.google_signin_service import GoogleIdentity
from app.services.owner_auth_service import OwnerAuthService, SESSION_COOKIE_NAME
from app.database.repositories.user_memory_repository import InMemoryUserRepository


@pytest.fixture
def user_repo() -> InMemoryUserRepository:
    repo = InMemoryUserRepository()
    repo.clear()
    return repo


@pytest.fixture
def gate_settings() -> Settings:
    return Settings(
        app_env="test",
        debug=True,
        allowed_owner_emails="kapil.singh20591@gmail.com",
        session_secret_key="test-session-secret",
        google_signin_client_id="test-client-id",
    )


@pytest.fixture
def no_gate_settings() -> Settings:
    # Explicit None matters: without it, this picks up whatever
    # ALLOWED_OWNER_EMAILS happens to be set to in the real local .env, which
    # defeats the point of this "gate disabled" regression guard.
    return Settings(app_env="test", debug=True, allowed_owner_emails=None)


@pytest.mark.asyncio
async def test_google_signin_rejects_unallowed_email(
    gate_settings: Settings, user_repo: InMemoryUserRepository
) -> None:
    app = create_app(settings=gate_settings)
    auth = OwnerAuthService(gate_settings, user_repo=user_repo)
    app.dependency_overrides[get_owner_auth_service] = lambda: auth
    app.dependency_overrides[get_user_repository] = lambda: user_repo

    identity = GoogleIdentity(
        sub="sub-1", email="someone-else@gmail.com", email_verified=True, name=None, picture=None
    )
    with patch(
        "app.services.owner_auth_service.verify_google_id_token",
        AsyncMock(return_value=identity),
    ):
        client = TestClient(app)
        response = client.post(
            f"{gate_settings.api_prefix}/auth/google/signin", json={"id_token": "fake"}
        )

    assert response.status_code == 403
    assert SESSION_COOKIE_NAME not in response.cookies


@pytest.mark.asyncio
async def test_google_signin_issues_session_cookie_for_allowed_email(
    gate_settings: Settings, user_repo: InMemoryUserRepository
) -> None:
    app = create_app(settings=gate_settings)
    auth = OwnerAuthService(gate_settings, user_repo=user_repo)
    app.dependency_overrides[get_owner_auth_service] = lambda: auth
    app.dependency_overrides[get_user_repository] = lambda: user_repo

    identity = GoogleIdentity(
        sub="sub-1",
        email="kapil.singh20591@gmail.com",
        email_verified=True,
        name="Kapil",
        picture=None,
    )
    with patch(
        "app.services.owner_auth_service.verify_google_id_token",
        AsyncMock(return_value=identity),
    ):
        client = TestClient(app)
        response = client.post(
            f"{gate_settings.api_prefix}/auth/google/signin", json={"id_token": "fake"}
        )

    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert SESSION_COOKIE_NAME in response.cookies

    me = client.get(f"{gate_settings.api_prefix}/auth/me")
    assert me.json()["authenticated"] is True
    assert me.json()["email"] == "kapil.singh20591@gmail.com"


def test_protected_route_401s_without_session_when_gate_configured(
    gate_settings: Settings, user_repo: InMemoryUserRepository
) -> None:
    app = create_app(settings=gate_settings)
    auth = OwnerAuthService(gate_settings, user_repo=user_repo)
    app.dependency_overrides[get_owner_auth_service] = lambda: auth
    app.dependency_overrides[get_user_repository] = lambda: user_repo

    client = TestClient(app)
    response = client.get(f"{gate_settings.api_prefix}/reports")

    assert response.status_code == 401


def test_protected_route_open_when_gate_not_configured(no_gate_settings: Settings) -> None:
    """Regression guard: the gate must no-op entirely when ALLOWED_OWNER_EMAILS is unset."""
    app = create_app(settings=no_gate_settings)
    client = TestClient(app)

    response = client.get(f"{no_gate_settings.api_prefix}/reports")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_logout_clears_cookie(
    gate_settings: Settings, user_repo: InMemoryUserRepository
) -> None:
    app = create_app(settings=gate_settings)
    auth = OwnerAuthService(gate_settings, user_repo=user_repo)
    app.dependency_overrides[get_owner_auth_service] = lambda: auth
    app.dependency_overrides[get_user_repository] = lambda: user_repo

    identity = GoogleIdentity(
        sub="sub-1",
        email="kapil.singh20591@gmail.com",
        email_verified=True,
        name=None,
        picture=None,
    )
    with patch(
        "app.services.owner_auth_service.verify_google_id_token",
        AsyncMock(return_value=identity),
    ):
        client = TestClient(app)
        client.post(f"{gate_settings.api_prefix}/auth/google/signin", json={"id_token": "fake"})

    logout_response = client.post(f"{gate_settings.api_prefix}/auth/logout")
    assert logout_response.status_code == 200

    me = client.get(f"{gate_settings.api_prefix}/auth/me")
    assert me.json()["authenticated"] is False


def test_session_token_rejects_tampered_token(
    gate_settings: Settings, user_repo: InMemoryUserRepository
) -> None:
    auth = OwnerAuthService(gate_settings, user_repo=user_repo)
    token = auth.create_session_token("owner-1", "kapil.singh20591@gmail.com")

    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    assert auth.verify_session_token(tampered) is None


def test_session_token_rejects_expired_token(user_repo: InMemoryUserRepository) -> None:
    settings = Settings(
        app_env="test",
        debug=True,
        allowed_owner_emails="kapil.singh20591@gmail.com",
        session_secret_key="test-session-secret",
        session_max_age_days=0,
    )
    auth = OwnerAuthService(settings, user_repo=user_repo)
    token = auth.create_session_token("owner-1", "kapil.singh20591@gmail.com")

    import time

    time.sleep(1.1)
    assert auth.verify_session_token(token) is None
