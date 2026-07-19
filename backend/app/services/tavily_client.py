"""Async HTTP client for Tavily Search API."""

from typing import Any

import httpx

from app.utils.exceptions import ExternalServiceError
from app.utils.logging import get_logger

logger = get_logger(__name__)

TAVILY_BASE_URL = "https://api.tavily.com"


class TavilyClient:
    """Low-level Tavily client – search only, no business logic."""

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(base_url=TAVILY_BASE_URL, timeout=30.0)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search(
        self,
        query: str,
        *,
        max_results: int = 8,
        search_depth: str = "advanced",
        topic: str = "news",
    ) -> list[dict[str, Any]]:
        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "topic": topic,
            "include_answer": False,
        }
        try:
            response = await self._client.post("/search", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Tavily HTTP error: %s", exc)
            raise ExternalServiceError("Tavily search request failed") from exc
        except httpx.RequestError as exc:
            logger.error("Tavily network error: %s", exc)
            raise ExternalServiceError("Tavily network error") from exc

        data = response.json()
        return data.get("results", [])
