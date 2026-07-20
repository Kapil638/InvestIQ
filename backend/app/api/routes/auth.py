"""Owner authentication endpoints: Google Sign-In + WebAuthn passkey unlock.

This router mixes public and protected endpoints, so unlike every other
router it is registered in main.py with NO blanket router-level dependency —
the two register/* routes take Depends(require_owner_session) directly.
"""

import json

from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies import (
    get_owner_auth_service,
    get_user_repository,
    require_owner_session,
    resolve_settings,
)
from app.core.config import Settings
from app.database.repositories.base import UserRepository
from app.schemas.auth import (
    AuthStatusResponse,
    GoogleSignInRequest,
    WebAuthnAuthenticateVerifyRequest,
    WebAuthnRegisterVerifyRequest,
)
from app.services.owner_auth_service import (
    CHALLENGE_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    OwnerAuthService,
    OwnerSessionData,
)
from app.services.webauthn_service import (
    generate_authentication_options_for,
    generate_registration_options_for,
    verify_authentication,
    verify_registration,
)
from app.utils.exceptions import OwnerNotAllowedError, WebAuthnError
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.session_max_age_days * 86400,
        path="/",
    )


def _set_challenge_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=CHALLENGE_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=300,
        path="/",
    )


def _clear_challenge_cookie(response: Response) -> None:
    response.delete_cookie(CHALLENGE_COOKIE_NAME, path="/")


@router.get("/me", response_model=AuthStatusResponse)
async def auth_me(
    request: Request,
    settings: Settings = Depends(resolve_settings),
    owner_auth: OwnerAuthService = Depends(get_owner_auth_service),
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthStatusResponse:
    """Always 200 — check `authenticated`. This is useAuthStatus()'s polling target."""
    if not settings.owner_auth_configured:
        return AuthStatusResponse(authenticated=False, owner_auth_configured=False)

    token = request.cookies.get(SESSION_COOKIE_NAME)
    session = owner_auth.verify_session_token(token) if token else None
    if session is None:
        return AuthStatusResponse(authenticated=False, owner_auth_configured=True)

    owner = await user_repo.get_owner_by_id(session.owner_id)
    credentials = await user_repo.list_credentials(session.owner_id)

    return AuthStatusResponse(
        authenticated=True,
        owner_auth_configured=True,
        email=owner.email if owner else session.email,
        display_name=owner.display_name if owner else None,
        picture_url=owner.picture_url if owner else None,
        has_passkey=len(credentials) > 0,
    )


@router.post("/google/signin", response_model=AuthStatusResponse)
async def google_signin(
    body: GoogleSignInRequest,
    response: Response,
    settings: Settings = Depends(resolve_settings),
    owner_auth: OwnerAuthService = Depends(get_owner_auth_service),
) -> AuthStatusResponse:
    user, token = await owner_auth.sign_in_with_google(body.id_token)
    _set_session_cookie(response, token, settings)

    return AuthStatusResponse(
        authenticated=True,
        owner_auth_configured=True,
        email=user.email,
        display_name=user.display_name,
        picture_url=user.picture_url,
        has_passkey=False,
    )


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"success": True}


@router.post("/webauthn/register/options")
async def webauthn_register_options(
    response: Response,
    settings: Settings = Depends(resolve_settings),
    owner_auth: OwnerAuthService = Depends(get_owner_auth_service),
    user_repo: UserRepository = Depends(get_user_repository),
    session: OwnerSessionData = Depends(require_owner_session),
) -> dict:
    owner = await user_repo.get_owner_by_id(session.owner_id)
    if owner is None:
        raise OwnerNotAllowedError("Owner account not found.")

    existing = await user_repo.list_credentials(session.owner_id)
    options_json, challenge = generate_registration_options_for(owner, existing, settings)

    _set_challenge_cookie(response, owner_auth.create_challenge_token(challenge), settings)
    return json.loads(options_json)


@router.post("/webauthn/register/verify")
async def webauthn_register_verify(
    body: WebAuthnRegisterVerifyRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(resolve_settings),
    owner_auth: OwnerAuthService = Depends(get_owner_auth_service),
    user_repo: UserRepository = Depends(get_user_repository),
    session: OwnerSessionData = Depends(require_owner_session),
) -> dict:
    challenge_token = request.cookies.get(CHALLENGE_COOKIE_NAME)
    challenge = owner_auth.verify_challenge_token(challenge_token) if challenge_token else None
    if challenge is None:
        raise WebAuthnError("Registration challenge expired or missing. Please try again.")

    credential_id, public_key, sign_count = verify_registration(
        body.credential, challenge, settings
    )
    await user_repo.add_credential(
        owner_id=session.owner_id,
        credential_id=credential_id,
        public_key=public_key,
        sign_count=sign_count,
        transports=body.credential.get("response", {}).get("transports", []) or [],
        device_label=body.device_label,
    )
    _clear_challenge_cookie(response)
    return {"success": True}


@router.post("/webauthn/authenticate/options")
async def webauthn_authenticate_options(
    response: Response,
    settings: Settings = Depends(resolve_settings),
    owner_auth: OwnerAuthService = Depends(get_owner_auth_service),
    user_repo: UserRepository = Depends(get_user_repository),
) -> dict:
    # Public/pre-login: single-owner scope, so list ALL registered credentials
    # without needing to know who's asking yet (see UserRepository.list_credentials).
    credentials = await user_repo.list_credentials()
    options_json, challenge = generate_authentication_options_for(credentials, settings)

    _set_challenge_cookie(response, owner_auth.create_challenge_token(challenge), settings)
    return json.loads(options_json)


@router.post("/webauthn/authenticate/verify", response_model=AuthStatusResponse)
async def webauthn_authenticate_verify(
    body: WebAuthnAuthenticateVerifyRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(resolve_settings),
    owner_auth: OwnerAuthService = Depends(get_owner_auth_service),
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthStatusResponse:
    challenge_token = request.cookies.get(CHALLENGE_COOKIE_NAME)
    challenge = owner_auth.verify_challenge_token(challenge_token) if challenge_token else None
    if challenge is None:
        raise WebAuthnError("Authentication challenge expired or missing. Please try again.")

    credential_id = body.credential.get("id")
    if not credential_id:
        raise WebAuthnError("Credential response missing id.")

    stored = await user_repo.get_credential(credential_id)
    if stored is None:
        raise WebAuthnError("Unknown passkey credential.")

    new_sign_count = verify_authentication(
        body.credential, challenge, stored.public_key, stored.sign_count, settings
    )
    await user_repo.update_sign_count(credential_id, new_sign_count)

    owner = await user_repo.get_owner_by_id(stored.owner_id)
    if owner is None:
        raise OwnerNotAllowedError("Owner account not found.")

    token = owner_auth.create_session_token(owner.id, owner.email)
    _set_session_cookie(response, token, settings)
    _clear_challenge_cookie(response)

    return AuthStatusResponse(
        authenticated=True,
        owner_auth_configured=True,
        email=owner.email,
        display_name=owner.display_name,
        picture_url=owner.picture_url,
        has_passkey=True,
    )
