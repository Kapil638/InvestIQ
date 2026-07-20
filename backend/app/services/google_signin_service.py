"""Verify Google Sign-In ID tokens for the owner authentication gate.

Distinct from google_drive_auth_service.py: Drive uses an authorization-code
redirect flow to authorize outbound Drive API calls. Sign-In uses Google
Identity Services' ID-token flow to identify the InvestIQ owner. Reuses
google-auth's id_token verifier (already a dependency for Drive) — no new
backend dependency needed for this part.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import Settings
from app.utils.exceptions import GoogleSignInError
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str | None
    picture: str | None


async def verify_google_id_token(token: str, settings: Settings) -> GoogleIdentity:
    if not settings.google_signin_configured:
        raise GoogleSignInError("GOOGLE_SIGNIN_CLIENT_ID is not configured.")

    def _verify() -> dict:
        try:
            return google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                audience=settings.google_signin_client_id,
            )
        except ValueError as exc:
            raise GoogleSignInError(f"Google Sign-In token verification failed: {exc}") from exc

    claims = await asyncio.to_thread(_verify)

    if not claims.get("email_verified", False):
        raise GoogleSignInError("Google account email is not verified.")

    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise GoogleSignInError("Google token response missing sub or email.")

    return GoogleIdentity(
        sub=str(sub),
        email=str(email),
        email_verified=True,
        name=claims.get("name"),
        picture=claims.get("picture"),
    )
