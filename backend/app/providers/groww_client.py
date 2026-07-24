"""Async wrapper over the synchronous growwapi SDK.

No OAuth/browser flow like Kite: GROWW_API_KEY/GROWW_API_SECRET mint an access
token directly (GrowwAPI.get_access_token), server-side, on demand. The token
is cached in-process and re-minted once on the first authentication failure —
this avoids hardcoding the exact "expires daily at 6 AM" boundary, since it
just self-heals on the next call.

Read-only by construction: this module never imports or calls place_order,
modify_order, cancel_order, or their "smart order" (GTT/OCO) equivalents.
"""

from __future__ import annotations

import asyncio

from growwapi import GrowwAPI
from growwapi.groww.exceptions import GrowwAPIAuthenticationException, GrowwAPIException

from app.core.config import Settings
from app.utils.exceptions import GrowwServiceError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GrowwClient:
    """Lazily mints and caches a GrowwAPI client from static key/secret credentials."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: GrowwAPI | None = None
        self._lock = asyncio.Lock()

    async def _get_client(self, *, force_remint: bool = False) -> GrowwAPI:
        if self._client is not None and not force_remint:
            return self._client

        async with self._lock:
            if self._client is not None and not force_remint:
                return self._client

            api_key = self._settings.groww_api_key
            api_secret = self._settings.groww_api_secret
            if not api_key or not api_secret:
                raise GrowwServiceError("GROWW_API_KEY/GROWW_API_SECRET are not configured.")

            try:
                token = await asyncio.to_thread(
                    GrowwAPI.get_access_token, api_key=api_key, secret=api_secret
                )
            except GrowwAPIException as exc:
                raise GrowwServiceError(
                    f"Groww access token request failed: {exc}. Regenerate the key/secret "
                    "at groww.in/trade-api/api-keys and update GROWW_API_KEY/GROWW_API_SECRET."
                ) from exc

            self._client = GrowwAPI(token)
            return self._client

    async def _call(self, method_name: str, /, **kwargs: object) -> dict:
        client = await self._get_client()
        try:
            return await asyncio.to_thread(getattr(client, method_name), **kwargs)
        except GrowwAPIAuthenticationException:
            logger.info("Groww access token expired — re-minting once and retrying %s", method_name)
            client = await self._get_client(force_remint=True)
            try:
                return await asyncio.to_thread(getattr(client, method_name), **kwargs)
            except GrowwAPIException as exc:
                raise GrowwServiceError(f"Groww {method_name} failed after token refresh: {exc}") from exc
        except GrowwAPIException as exc:
            raise GrowwServiceError(f"Groww {method_name} failed: {exc}") from exc

    async def get_profile(self) -> dict:
        return await self._call("get_user_profile")

    async def get_holdings(self) -> dict:
        return await self._call("get_holdings_for_user")

    async def get_positions(self) -> dict:
        return await self._call("get_positions_for_user")

    async def get_margin(self) -> dict:
        return await self._call("get_available_margin_details")
