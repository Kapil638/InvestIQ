"""
Tapetide MCP provider – read-only HTTP client for Tapetide NSE/BSE market data.

Connects to the remote Tapetide MCP server (or a compatible HTTP endpoint) using
Bearer authentication. Tokens are never logged.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.utils.exceptions import TapetideMcpNotEnabledError, TapetideMcpServiceError
from app.utils.logging import get_logger

logger = get_logger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "InvestIQ"
CLIENT_VERSION = "1.0.0"

READ_TOOL_NAMES = frozenset(
    {
        "search_stocks",
        "screen_stocks",
        "screen_stocks_technical",
        "get_screener_ratios",
        "get_trending_stocks",
        "get_company_profile",
        "get_stock_events",
        "get_stock_ownership",
        "get_stock_quote",
        "get_batch_quotes",
        "get_price_history",
        "get_financials",
        "get_shareholding",
        "get_forecasts",
        "get_market_pulse",
        "get_fii_dii_detail",
        "get_fpi_sectors",
        "get_market_news",
        "market_valuations",
        "market_deals",
        "market_fno_ban",
        "market_ipo",
        "market_deliveries",
        "market_mtf",
        "market_slbm",
        "market_signals",
        "market_heatmap",
        "get_user_portfolio",
        "get_watchlist",
    }
)


class TapetideMcpProvider:
    """Low-level MCP client for Tapetide read-only Indian market data."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http_client
        self._owns_client = http_client is None
        self._initialized = False
        self._rpc_id = 0
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0

    @property
    def enabled(self) -> bool:
        return self._settings.tapetide_mcp_enabled

    @property
    def read_only(self) -> bool:
        return self._settings.tapetide_mcp_read_only

    def assert_enabled(self) -> None:
        if not self.enabled:
            raise TapetideMcpNotEnabledError("Tapetide NSE/BSE MCP is not enabled.")

    def is_tool_allowed(self, tool_name: str) -> bool:
        if not self.read_only:
            return True
        return tool_name in READ_TOOL_NAMES

    def assert_tool_allowed(self, tool_name: str) -> None:
        self.assert_enabled()
        if not self.is_tool_allowed(tool_name):
            raise TapetideMcpServiceError(f"Tapetide MCP tool '{tool_name}' is not allowed.")

    async def aclose(self) -> None:
        if self._owns_client and self._http is not None:
            await self._http.aclose()
            self._http = None

    def _mcp_base_url(self) -> str:
        url = self._settings.tapetide_mcp_url.rstrip("/")
        if url.endswith("/mcp"):
            return url[: -len("/mcp")]
        return url

    def _mcp_endpoint(self) -> str:
        url = self._settings.tapetide_mcp_url.rstrip("/")
        return url if url.endswith("/mcp") else f"{url}/mcp"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None:
            timeout = float(self._settings.tapetide_mcp_timeout_seconds)
            self._http = httpx.AsyncClient(timeout=timeout)
        return self._http

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    async def _get_bearer_token(self, *, force_refresh: bool = False) -> str:
        if (
            not force_refresh
            and self._access_token
            and time.monotonic() < self._access_token_expires_at
        ):
            return self._access_token

        api_token = self._settings.tapetide_api_token
        if not api_token or not api_token.strip():
            raise TapetideMcpServiceError("Tapetide API token is not configured.")

        client = await self._get_client()
        token_url = f"{self._mcp_base_url()}/token"
        try:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": api_token.strip(),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.HTTPError as exc:
            raise TapetideMcpServiceError(f"Tapetide token refresh failed: {exc}") from exc

        if response.status_code >= 400:
            # Fall back to using the configured token directly as Bearer.
            return api_token.strip()

        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise TapetideMcpServiceError("Tapetide token endpoint returned invalid JSON") from exc

        access_token = str(body.get("access_token") or "").strip()
        if not access_token:
            return api_token.strip()

        expires_in = int(body.get("expires_in") or 3600)
        self._access_token = access_token
        self._access_token_expires_at = time.monotonic() + max(expires_in - 300, 60)
        return access_token

    async def _post_message(self, payload: dict[str, Any], *, retry_auth: bool = True) -> dict[str, Any]:
        client = await self._get_client()
        token = await self._get_bearer_token()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
        }

        try:
            response = await client.post(self._mcp_endpoint(), json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise TapetideMcpServiceError(f"Tapetide MCP request failed: {exc}") from exc

        if response.status_code == 401 and retry_auth:
            token = await self._get_bearer_token(force_refresh=True)
            headers["Authorization"] = f"Bearer {token}"
            try:
                response = await client.post(self._mcp_endpoint(), json=payload, headers=headers)
            except httpx.HTTPError as exc:
                raise TapetideMcpServiceError(f"Tapetide MCP request failed: {exc}") from exc

        if response.status_code >= 400:
            raise TapetideMcpServiceError(
                f"Tapetide MCP HTTP {response.status_code}: {response.text[:300]}"
            )

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse_json(response.text)

        if not response.content:
            return {}

        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise TapetideMcpServiceError("Tapetide MCP returned invalid JSON") from exc

        if isinstance(body, list):
            for item in body:
                if isinstance(item, dict) and ("result" in item or "error" in item):
                    return item
            return body[0] if body else {}

        return body

    @staticmethod
    def _parse_sse_json(text: str) -> dict[str, Any]:
        last_valid: dict[str, Any] | None = None
        for line in text.splitlines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                last_valid = parsed
        if last_valid is not None:
            return last_valid
        raise TapetideMcpServiceError("Tapetide MCP SSE response did not contain JSON data")

    async def initialize(self) -> None:
        if self._initialized:
            return

        init_payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            },
        }
        result = await self._post_message(init_payload)
        if "error" in result:
            raise TapetideMcpServiceError(self._format_rpc_error(result["error"]))

        await self._post_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True

    async def list_tools(self) -> list[dict[str, Any]]:
        self.assert_enabled()
        await self.initialize()
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {},
        }
        result = await self._post_message(payload)
        if "error" in result:
            raise TapetideMcpServiceError(self._format_rpc_error(result["error"]))

        tools = result.get("result", {}).get("tools", [])
        return tools if isinstance(tools, list) else []

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        self.assert_tool_allowed(tool_name)
        await self.initialize()

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments or {}},
        }
        result = await self._post_message(payload)
        if "error" in result:
            raise TapetideMcpServiceError(self._format_rpc_error(result["error"]))

        tool_result = result.get("result", {})
        if isinstance(tool_result, dict) and tool_result.get("isError"):
            message = _extract_error_text(tool_result)
            raise TapetideMcpServiceError(message or f"Tapetide MCP tool '{tool_name}' failed")

        return self._extract_tool_result(tool_result)

    async def health_check(self) -> bool:
        if not self.enabled:
            return False
        if not self._settings.tapetide_token_configured:
            return False
        try:
            await self.list_tools()
            return True
        except TapetideMcpServiceError as exc:
            logger.debug("Tapetide MCP health check failed: %s", exc)
            return False

    @staticmethod
    def _format_rpc_error(error: Any) -> str:
        if isinstance(error, dict):
            message = error.get("message", "Unknown MCP error")
            code = error.get("code")
            return f"{message} (code={code})" if code is not None else str(message)
        return str(error)

    @staticmethod
    def _extract_tool_result(result: dict[str, Any]) -> Any:
        if not result:
            return None

        if "structuredContent" in result and result["structuredContent"] is not None:
            return result["structuredContent"]

        content = result.get("content")
        if isinstance(content, list):
            texts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(str(block.get("text", "")))
            joined = "\n".join(text for text in texts if text).strip()
            if joined:
                try:
                    return json.loads(joined)
                except json.JSONDecodeError:
                    return joined

        return result

    def available_read_tools(self, discovered: list[dict[str, Any]] | None = None) -> list[str]:
        names = [str(tool.get("name", "")) for tool in (discovered or []) if tool.get("name")]
        if not names:
            names = sorted(READ_TOOL_NAMES)
        return [name for name in names if self.is_tool_allowed(name)]


def _extract_error_text(result: dict[str, Any]) -> str | None:
    content = result.get("content")
    if isinstance(content, list) and content:
        block = content[0]
        if isinstance(block, dict) and block.get("type") == "text":
            return str(block.get("text", "")).strip() or None
    return None
