"""WebAuthn/passkey registration and authentication ceremonies.

Wraps the `webauthn` (py_webauthn) package rather than hand-rolling CBOR/COSE/
signature verification — unlike the OAuth flows elsewhere in this app, getting
WebAuthn's cryptographic verification subtly wrong is a real security risk, not
just a style tradeoff.

API surface confirmed against the installed webauthn==3.0.0 at implementation
time (do not assume this matches other major versions).
"""

from __future__ import annotations

import base64

import webauthn
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core.config import Settings
from app.models.owner_user import OwnerUser, WebAuthnCredential
from app.utils.exceptions import WebAuthnError
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _public_key_descriptors(credentials: list[WebAuthnCredential]) -> list[PublicKeyCredentialDescriptor]:
    descriptors = []
    for cred in credentials:
        transports = [
            AuthenticatorTransport(t) for t in cred.transports if t in {tr.value for tr in AuthenticatorTransport}
        ]
        descriptors.append(
            PublicKeyCredentialDescriptor(
                id=webauthn.base64url_to_bytes(cred.credential_id),
                transports=transports or None,
            )
        )
    return descriptors


def generate_registration_options_for(
    owner: OwnerUser,
    existing_credentials: list[WebAuthnCredential],
    settings: Settings,
) -> tuple[str, bytes]:
    """Returns (options_json_for_frontend, raw_challenge_bytes_to_stash_in_a_cookie)."""
    options = webauthn.generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=owner.id.encode("utf-8"),
        user_name=owner.email,
        user_display_name=owner.display_name or owner.email,
        exclude_credentials=_public_key_descriptors(existing_credentials),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    return webauthn.options_to_json(options), options.challenge


def verify_registration(
    credential_json: dict,
    expected_challenge: bytes,
    settings: Settings,
) -> tuple[str, str, int]:
    """Returns (credential_id_b64url, public_key_b64url, sign_count)."""
    try:
        verified = webauthn.verify_registration_response(
            credential=credential_json,
            expected_challenge=expected_challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
        )
    except Exception as exc:
        raise WebAuthnError(f"Passkey registration verification failed: {exc}") from exc

    credential_id_b64url = base64.urlsafe_b64encode(verified.credential_id).rstrip(b"=").decode()
    public_key_b64url = base64.urlsafe_b64encode(verified.credential_public_key).rstrip(b"=").decode()
    return credential_id_b64url, public_key_b64url, verified.sign_count


def generate_authentication_options_for(
    credentials: list[WebAuthnCredential],
    settings: Settings,
) -> tuple[str, bytes]:
    """Returns (options_json_for_frontend, raw_challenge_bytes_to_stash_in_a_cookie)."""
    if not credentials:
        raise WebAuthnError("No passkeys are registered yet.")

    options = webauthn.generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=_public_key_descriptors(credentials),
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    return webauthn.options_to_json(options), options.challenge


def verify_authentication(
    credential_json: dict,
    expected_challenge: bytes,
    stored_public_key_b64url: str,
    stored_sign_count: int,
    settings: Settings,
) -> int:
    """Returns the new sign_count to persist."""
    try:
        verified = webauthn.verify_authentication_response(
            credential=credential_json,
            expected_challenge=expected_challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            credential_public_key=webauthn.base64url_to_bytes(stored_public_key_b64url),
            credential_current_sign_count=stored_sign_count,
        )
    except Exception as exc:
        raise WebAuthnError(f"Passkey authentication verification failed: {exc}") from exc

    return verified.new_sign_count
