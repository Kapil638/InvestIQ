"""Async HTTP client for Financial Modeling Prep API."""

from typing import Any

import httpx

from app.utils.exceptions import ExternalServiceError, TickerNotFoundError
from app.utils.logging import get_logger

logger = get_logger(__name__)

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"


class FMPClient:
    """Low-level client – only knows how to talk to FMP, not business rules."""

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(base_url=FMP_BASE_URL, timeout=30.0)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = {"apikey": self._api_key, **(params or {})}
        try:
            response = await self._client.get(path, params=query)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("FMP HTTP error for %s: %s", path, exc)
            raise ExternalServiceError(f"FMP request failed: {path}") from exc
        except httpx.RequestError as exc:
            logger.error("FMP network error for %s: %s", path, exc)
            raise ExternalServiceError(f"FMP network error: {path}") from exc

        data = response.json()
        if isinstance(data, dict) and data.get("Error Message"):
            raise ExternalServiceError(str(data["Error Message"]))
        return data

    async def get_profile(self, ticker: str) -> dict[str, Any]:
        data = await self._get(f"/profile/{ticker.upper()}")
        if not data:
            raise TickerNotFoundError(f"No FMP profile found for ticker: {ticker}")
        return data[0]

    async def get_income_statements(self, ticker: str, limit: int = 4) -> list[dict[str, Any]]:
        return await self._get(f"/income-statement/{ticker.upper()}", {"limit": limit})

    async def get_balance_sheets(self, ticker: str, limit: int = 4) -> list[dict[str, Any]]:
        return await self._get(f"/balance-sheet-statement/{ticker.upper()}", {"limit": limit})

    async def get_cash_flow_statements(self, ticker: str, limit: int = 4) -> list[dict[str, Any]]:
        return await self._get(f"/cash-flow-statement/{ticker.upper()}", {"limit": limit})

    async def get_ratios(self, ticker: str, limit: int = 4) -> list[dict[str, Any]]:
        return await self._get(f"/ratios/{ticker.upper()}", {"limit": limit})

    async def get_key_metrics(self, ticker: str, limit: int = 4) -> list[dict[str, Any]]:
        return await self._get(f"/key-metrics/{ticker.upper()}", {"limit": limit})
