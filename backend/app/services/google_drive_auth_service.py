"""Google Drive OAuth login and callback handling (user delegation)."""

from __future__ import annotations

import secrets as secrets_module

from app.core.config import Settings
from app.providers.google_oauth_client import GoogleOAuthClient, expiry_from_expires_in
from app.services.google_drive_token_store import (
    GoogleDriveOAuthSession,
    GoogleDriveTokenStore,
    get_google_drive_token_store,
)
from app.utils.exceptions import GoogleDriveAuthError
from app.utils.logging import get_logger

logger = get_logger(__name__)

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
]

# Process-wide, not per-instance: a fresh GoogleDriveAuthService is constructed via
# DI for every request (see build_google_drive_auth_service), so state set during
# /login must survive to the separate instance that handles /callback.
_pending_state: str | None = None


class GoogleDriveAuthService:
    """Manages Google Drive OAuth – tokens never leave the server."""

    def __init__(
        self,
        settings: Settings,
        token_store: GoogleDriveTokenStore | None = None,
        oauth_client: GoogleOAuthClient | None = None,
    ) -> None:
        self._settings = settings
        self._token_store = token_store or get_google_drive_token_store()
        self._client = oauth_client or GoogleOAuthClient(settings)

    @property
    def token_store(self) -> GoogleDriveTokenStore:
        return self._token_store

    @property
    def is_enabled(self) -> bool:
        return self._settings.google_drive_enabled

    def is_configured(self) -> bool:
        return self._settings.google_drive_oauth_configured

    def is_authenticated(self) -> bool:
        return self._token_store.is_authenticated()

    def get_user_email(self) -> str | None:
        session = self._token_store.get_session()
        return session.user_email if session else None

    def get_login_url(self) -> str:
        global _pending_state
        if not self._settings.google_drive_enabled:
            raise GoogleDriveAuthError("Google Drive is not enabled.")
        state = secrets_module.token_urlsafe(24)
        _pending_state = state
        return self._client.build_authorization_url(state=state)

    def get_frontend_redirect_url(self, *, success: bool = True) -> str:
        base = self._settings.google_drive_oauth_frontend_redirect_url.rstrip("/")
        if success:
            return f"{base}?drive_connected=1"
        return f"{base}?drive_error=1"

    async def handle_callback(self, code: str | None, state: str | None, error: str | None) -> None:
        global _pending_state
        if error:
            raise GoogleDriveAuthError(f"Google Drive authorization was cancelled: {error}")
        if not code:
            raise GoogleDriveAuthError("Missing authorization code from Google callback.")
        if _pending_state is not None and state != _pending_state:
            raise GoogleDriveAuthError("Google Drive authorization state mismatch.")
        _pending_state = None

        token_response = await self._client.exchange_code(code)
        access_token = token_response["access_token"]
        refresh_token = token_response["refresh_token"]
        expiry = expiry_from_expires_in(token_response.get("expires_in"))
        scope_str = token_response.get("scope", "")
        scopes = scope_str.split(" ") if scope_str else DRIVE_SCOPES

        user_email = await self._client.fetch_user_email(access_token)

        session = GoogleDriveOAuthSession(
            access_token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self._settings.google_drive_oauth_client_id or "",
            client_secret=self._settings.google_drive_oauth_client_secret or "",
            scopes=scopes,
            expiry=expiry.isoformat(),
            user_email=user_email,
        )
        self._token_store.set_session(session)
        logger.info("Google Drive OAuth session established for %s", user_email or "unknown user")

    def logout(self) -> None:
        self._token_store.clear()
