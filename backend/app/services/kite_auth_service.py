"""Zerodha OAuth login and callback handling."""

from __future__ import annotations

from app.core.config import Settings
from app.providers.kite_connect_client import KiteConnectClient
from app.services.kite_token_store import KiteTokenStore, get_kite_token_store
from app.utils.exceptions import KiteAuthError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class KiteAuthService:
    """Manages Zerodha OAuth – tokens never leave the server."""

    def __init__(
        self,
        settings: Settings,
        token_store: KiteTokenStore | None = None,
        connect_client: KiteConnectClient | None = None,
    ) -> None:
        self._settings = settings
        self._token_store = token_store or get_kite_token_store()
        self._client = connect_client or KiteConnectClient(settings, self._token_store)

    @property
    def token_store(self) -> KiteTokenStore:
        return self._token_store

    @property
    def connect_client(self) -> KiteConnectClient:
        return self._client

    def is_configured(self) -> bool:
        return self._settings.kite_oauth_configured

    def is_authenticated(self) -> bool:
        return self._token_store.is_authenticated()

    def get_user_id(self) -> str | None:
        session = self._token_store.get_session()
        return session.user_id if session else None

    def get_broker(self) -> str | None:
        session = self._token_store.get_session()
        if not session:
            return None
        return "Zerodha" if session.broker.upper() == "ZERODHA" else session.broker

    def get_login_url(self) -> str:
        if not self._settings.kite_mcp_enabled:
            raise KiteAuthError("Kite Connect is not enabled.")
        return self._client.build_login_url()

    def get_frontend_redirect_url(self, *, success: bool = True) -> str:
        base = self._settings.kite_frontend_redirect_url.rstrip("/")
        if success:
            return f"{base}?kite_connected=1"
        return f"{base}?kite_error=1"

    async def handle_callback(self, request_token: str | None, status: str | None) -> None:
        if status and status.lower() != "success":
            raise KiteAuthError("Zerodha login was cancelled or failed.")
        if not request_token:
            raise KiteAuthError("Missing request_token from Zerodha callback.")
        await self._client.exchange_request_token(request_token)

    async def validate_session(self) -> bool:
        """Confirm stored token is still valid via profile call."""
        if not self.is_authenticated():
            return False
        try:
            await self._client.get_profile()
            return True
        except KiteAuthError:
            return False
        except Exception as exc:
            logger.warning("Kite session validation failed: %s", exc)
            return False

    def logout(self) -> None:
        self._token_store.clear()
