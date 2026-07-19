"""Google OAuth 2.0 authorization-code flow for Drive user delegation.

Deliberately implemented with plain httpx (already a dependency, used the same
way as the Kite Connect client) rather than google-auth-oauthlib, to avoid
adding a new dependency for a flow that's just two HTTP calls.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings
from app.utils.exceptions import GoogleDriveAuthError
from app.utils.logging import get_logger

logger = get_logger(__name__)

GOOGLE_AUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
USERINFO_SCOPE = "https://www.googleapis.com/auth/userinfo.email"


class GoogleOAuthClient:
    """Handles the browser-redirect authorization-code exchange for Drive access."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _require_credentials(self) -> tuple[str, str]:
        client_id = self._settings.google_drive_oauth_client_id
        client_secret = self._settings.google_drive_oauth_client_secret
        if not client_id or not client_secret:
            raise GoogleDriveAuthError(
                "GOOGLE_DRIVE_OAUTH_CLIENT_ID and GOOGLE_DRIVE_OAUTH_CLIENT_SECRET are required."
            )
        return client_id, client_secret

    def build_authorization_url(self, *, state: str) -> str:
        client_id, _ = self._require_credentials()
        params = {
            "client_id": client_id,
            "redirect_uri": self._settings.google_drive_oauth_redirect_url,
            "response_type": "code",
            "scope": f"{DRIVE_SCOPE} {USERINFO_SCOPE}",
            "access_type": "offline",
            "prompt": "consent",  # forces a fresh refresh_token even on repeat consent
            "state": state,
        }
        return f"{GOOGLE_AUTH_BASE}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        client_id, client_secret = self._require_credentials()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": self._settings.google_drive_oauth_redirect_url,
                    "grant_type": "authorization_code",
                },
            )

        if response.status_code >= 400:
            logger.warning("Google Drive OAuth code exchange failed: %s", response.text[:300])
            raise GoogleDriveAuthError("Failed to exchange Google authorization code.")

        body = response.json()
        if "access_token" not in body:
            raise GoogleDriveAuthError("Google token response missing access_token.")
        if "refresh_token" not in body:
            # Happens if the user has already granted consent before and Google
            # skips issuing a new refresh_token despite prompt=consent in rare cases.
            raise GoogleDriveAuthError(
                "Google did not return a refresh_token. Revoke prior access at "
                "https://myaccount.google.com/permissions and try connecting again."
            )
        return body

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        client_id, client_secret = self._require_credentials()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                },
            )

        if response.status_code >= 400:
            logger.warning("Google Drive OAuth token refresh failed: %s", response.text[:300])
            raise GoogleDriveAuthError("Google Drive session expired. Please reconnect.")

        return response.json()

    async def fetch_user_email(self, access_token: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if response.status_code >= 400:
                return None
            return response.json().get("email")
        except Exception as exc:
            logger.debug("Could not fetch Google Drive account email: %s", exc)
            return None


def expiry_from_expires_in(expires_in: int | float | None) -> datetime:
    seconds = int(expires_in) if expires_in else 3600
    return datetime.now(UTC) + timedelta(seconds=seconds)
