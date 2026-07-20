"""Tests for WebAuthn/passkey registration and authentication endpoints.

Note: a full register->authenticate round trip requires a synthetic
ECDSA-signed attestation (real browser WebAuthn crypto can't be faked with a
simple mock). That's real implementation effort or should be done from
py_webauthn's own test fixtures, not attempted here — these tests cover the
parts that don't require fabricating valid signatures: auth requirements,
credential listing, and rejection of unknown/invalid credentials.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_owner_auth_service, get_user_repository
from app.core.config import Settings
from app.database.repositories.user_memory_repository import InMemoryUserRepository
from app.main import create_app
from app.services.owner_auth_service import OwnerAuthService, SESSION_COOKIE_NAME


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
        webauthn_rp_id="localhost",
        webauthn_origin="http://localhost:5173",
    )


def _app_with_session(gate_settings: Settings, user_repo: InMemoryUserRepository, owner_id: str):
    app = create_app(settings=gate_settings)
    auth = OwnerAuthService(gate_settings, user_repo=user_repo)
    app.dependency_overrides[get_owner_auth_service] = lambda: auth
    app.dependency_overrides[get_user_repository] = lambda: user_repo

    client = TestClient(app)
    token = auth.create_session_token(owner_id, "kapil.singh20591@gmail.com")
    client.cookies.set(SESSION_COOKIE_NAME, token)
    return client, auth


def test_register_options_requires_session(
    gate_settings: Settings, user_repo: InMemoryUserRepository
) -> None:
    app = create_app(settings=gate_settings)
    client = TestClient(app)

    response = client.post(f"{gate_settings.api_prefix}/auth/webauthn/register/options")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_options_succeeds_with_session(
    gate_settings: Settings, user_repo: InMemoryUserRepository
) -> None:
    owner = await user_repo.get_or_create_owner(
        google_sub="sub-1",
        email="kapil.singh20591@gmail.com",
        display_name="Kapil",
        picture_url=None,
    )
    client, _ = _app_with_session(gate_settings, user_repo, owner.id)

    response = client.post(f"{gate_settings.api_prefix}/auth/webauthn/register/options")

    assert response.status_code == 200
    body = response.json()
    assert body["rp"]["id"] == "localhost"
    assert "challenge" in body


@pytest.mark.asyncio
async def test_authenticate_options_lists_registered_credential_ids(
    gate_settings: Settings, user_repo: InMemoryUserRepository
) -> None:
    owner = await user_repo.get_or_create_owner(
        google_sub="sub-1",
        email="kapil.singh20591@gmail.com",
        display_name="Kapil",
        picture_url=None,
    )
    await user_repo.add_credential(
        owner_id=owner.id,
        credential_id="Y3JlZC0x",
        public_key="cGFzc2tleQ",
        sign_count=0,
        transports=["internal"],
        device_label="Test laptop",
    )

    app = create_app(settings=gate_settings)
    app.dependency_overrides[get_user_repository] = lambda: user_repo
    client = TestClient(app)

    response = client.post(f"{gate_settings.api_prefix}/auth/webauthn/authenticate/options")

    assert response.status_code == 200
    body = response.json()
    assert len(body["allowCredentials"]) == 1


def test_authenticate_options_fails_with_no_registered_credentials(
    gate_settings: Settings, user_repo: InMemoryUserRepository
) -> None:
    app = create_app(settings=gate_settings)
    app.dependency_overrides[get_user_repository] = lambda: user_repo
    client = TestClient(app)

    response = client.post(f"{gate_settings.api_prefix}/auth/webauthn/authenticate/verify", json={
        "credential": {"id": "unknown-cred-id", "rawId": "x", "type": "public-key", "response": {}},
    })

    # No challenge cookie was ever issued, so this must fail before even
    # reaching credential lookup.
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_authenticate_verify_rejects_unknown_credential_id(
    gate_settings: Settings, user_repo: InMemoryUserRepository
) -> None:
    app = create_app(settings=gate_settings)
    auth = OwnerAuthService(gate_settings, user_repo=user_repo)
    app.dependency_overrides[get_owner_auth_service] = lambda: auth
    app.dependency_overrides[get_user_repository] = lambda: user_repo
    client = TestClient(app)

    # Manually set a valid (but arbitrary) challenge cookie so we get past that
    # check and specifically exercise "unknown credential" rejection.
    challenge_token = auth.create_challenge_token(b"0" * 32)
    client.cookies.set("investiq_webauthn_challenge", challenge_token)

    response = client.post(
        f"{gate_settings.api_prefix}/auth/webauthn/authenticate/verify",
        json={
            "credential": {
                "id": "totally-unknown-credential-id",
                "rawId": "x",
                "type": "public-key",
                "response": {},
            }
        },
    )

    assert response.status_code == 400
    assert "Unknown passkey" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_sign_count_persists(user_repo: InMemoryUserRepository) -> None:
    owner = await user_repo.get_or_create_owner(
        google_sub="sub-1", email="kapil.singh20591@gmail.com", display_name=None, picture_url=None
    )
    await user_repo.add_credential(
        owner_id=owner.id,
        credential_id="cred-1",
        public_key="pk",
        sign_count=0,
        transports=[],
        device_label=None,
    )

    await user_repo.update_sign_count("cred-1", 7)

    updated = await user_repo.get_credential("cred-1")
    assert updated is not None
    assert updated.sign_count == 7
    assert updated.last_used_at is not None
