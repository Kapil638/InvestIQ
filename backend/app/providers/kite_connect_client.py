"""Zerodha Kite Connect REST client – uses server-stored access tokens only."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.kite import KiteHoldingItem, KitePositionItem
from app.services.kite_token_store import KiteSession, KiteTokenStore
from app.utils.exceptions import KiteAuthError, KiteServiceError
from app.utils.logging import get_logger

logger = get_logger(__name__)

KITE_API_BASE = "https://api.kite.trade"
KITE_LOGIN_BASE = "https://kite.zerodha.com/connect/login"


class KiteConnectClient:
    """Authenticated Kite Connect HTTP client."""

    def __init__(self, settings: Settings, token_store: KiteTokenStore) -> None:
        self._settings = settings
        self._token_store = token_store

    def _require_credentials(self) -> tuple[str, str]:
        api_key = self._settings.kite_api_key
        api_secret = self._settings.kite_api_secret
        if not api_key or not api_secret:
            raise KiteAuthError(
                "KITE_API_KEY and KITE_API_SECRET are required for Zerodha OAuth."
            )
        return api_key, api_secret

    def build_login_url(self) -> str:
        api_key, _ = self._require_credentials()
        return f"{KITE_LOGIN_BASE}?v=3&api_key={api_key}"

    async def exchange_request_token(self, request_token: str) -> KiteSession:
        api_key, api_secret = self._require_credentials()
        checksum = hashlib.sha256(f"{api_key}{request_token}{api_secret}".encode()).hexdigest()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{KITE_API_BASE}/session/token",
                data={
                    "api_key": api_key,
                    "request_token": request_token,
                    "checksum": checksum,
                },
            )

        if response.status_code >= 400:
            logger.warning("Kite token exchange failed: %s", response.text[:300])
            raise KiteAuthError("Failed to exchange Zerodha request token.")

        body = response.json()
        if body.get("status") != "success":
            raise KiteAuthError(body.get("message", "Zerodha token exchange failed."))

        data = body.get("data") or {}
        access_token = data.get("access_token")
        user_id = data.get("user_id")
        if not access_token or not user_id:
            raise KiteAuthError("Zerodha token response missing access_token or user_id.")

        session = KiteSession(
            access_token=str(access_token),
            user_id=str(user_id),
            user_name=data.get("user_name") or data.get("user_shortname"),
            broker=str(data.get("broker") or "ZERODHA"),
            login_time=_parse_login_time(data.get("login_time")),
            public_token=data.get("public_token"),
        )
        self._token_store.set_session(session)
        logger.info("Zerodha session established for user %s", session.user_id)
        return session

    async def get_profile(self) -> dict[str, Any]:
        return await self._get("/user/profile")

    async def get_holdings(self) -> list[KiteHoldingItem]:
        data = await self._get("/portfolio/holdings")
        if not isinstance(data, list):
            return []
        return [_map_holding(item) for item in data if isinstance(item, dict)]

    async def get_positions(self) -> tuple[list[KitePositionItem], list[KitePositionItem]]:
        data = await self._get("/portfolio/positions")
        if not isinstance(data, dict):
            return [], []
        net = [_map_position(item) for item in data.get("net", []) if isinstance(item, dict)]
        day = [_map_position(item) for item in data.get("day", []) if isinstance(item, dict)]
        return net, day

    async def get_quotes(self, instruments: list[str]) -> dict[str, Any]:
        if not instruments:
            return {}
        joined = ",".join(instruments)
        data = await self._get("/quote", params={"i": joined})
        return data if isinstance(data, dict) else {}

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        session = self._token_store.get_session()
        if not session:
            raise KiteAuthError("Zerodha authentication required.")

        api_key = self._settings.kite_api_key
        if not api_key:
            raise KiteAuthError("KITE_API_KEY is not configured.")

        headers = {"Authorization": f"token {api_key}:{session.access_token}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{KITE_API_BASE}{path}",
                headers=headers,
                params=params,
            )

        if response.status_code == 403:
            self._token_store.clear()
            raise KiteAuthError("Zerodha session expired. Please reconnect.")

        if response.status_code >= 400:
            raise KiteServiceError(f"Kite API error {response.status_code}: {response.text[:200]}")

        body = response.json()
        if body.get("status") != "success":
            message = body.get("message", "Kite API request failed")
            if "token" in message.lower() or "session" in message.lower():
                self._token_store.clear()
                raise KiteAuthError("Zerodha session expired. Please reconnect.")
            raise KiteServiceError(message)

        return body.get("data")


def _parse_login_time(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(UTC)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _map_holding(item: dict[str, Any]) -> KiteHoldingItem:
    return KiteHoldingItem(
        tradingsymbol=str(item.get("tradingsymbol") or item.get("symbol") or ""),
        exchange=item.get("exchange"),
        quantity=_as_float(item.get("quantity")),
        average_price=_as_float(item.get("average_price")),
        last_price=_as_float(item.get("last_price")),
        pnl=_as_float(item.get("pnl")),
        product=item.get("product"),
        day_change=_as_float(item.get("day_change_percentage") or item.get("day_change")),
    )


def _map_position(item: dict[str, Any]) -> KitePositionItem:
    return KitePositionItem(
        tradingsymbol=str(item.get("tradingsymbol") or item.get("symbol") or ""),
        exchange=item.get("exchange"),
        quantity=_as_float(item.get("quantity")),
        average_price=_as_float(item.get("average_price")),
        last_price=_as_float(item.get("last_price")),
        pnl=_as_float(item.get("pnl")),
        product=item.get("product"),
    )
