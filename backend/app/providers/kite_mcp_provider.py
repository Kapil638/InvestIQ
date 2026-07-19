"""
Kite MCP provider – read-only HTTP client for Zerodha Kite MCP server.

Uses MCP Streamable HTTP transport (JSON-RPC) against a hosted or self-hosted
Kite MCP endpoint. Never exposes tokens to callers; auth is handled by MCP.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from app.core.config import Settings
from app.utils.exceptions import KiteBlockedToolError, KiteNotEnabledError, KiteServiceError
from app.utils.logging import get_logger

logger = get_logger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "InvestIQ"
CLIENT_VERSION = "1.0.0"

# Trading / order tools – always blocked when read_only is true
TRADING_TOOL_NAMES = frozenset(
    {
        "place_order",
        "modify_order",
        "cancel_order",
        "place_gtt_order",
        "modify_gtt_order",
        "delete_gtt_order",
        "get_orders",
        "get_trades",
        "get_order_history",
        "get_order_trades",
        "get_gtts",
    }
)

READ_TOOL_NAMES = frozenset(
    {
        "get_quotes",
        "get_ltp",
        "get_ohlc",
        "get_historical_data",
        "search_instruments",
        "get_holdings",
        "get_positions",
        "get_profile",
        "get_margins",
        "get_mf_holdings",
        "login",
    }
)


class KiteMcpProvider:
    """Low-level MCP client for Kite Connect read operations."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http_client
        self._owns_client = http_client is None
        self._session_id: str | None = None
        self._initialized = False
        self._rpc_id = 0

    @property
    def enabled(self) -> bool:
        return self._settings.kite_mcp_enabled

    @property
    def read_only(self) -> bool:
        return self._settings.kite_mcp_read_only

    @property
    def excluded_tools(self) -> list[str]:
        return list(self._settings.kite_excluded_tools_list)

    def is_tool_allowed(self, tool_name: str) -> bool:
        if tool_name in self._settings.kite_excluded_tools_list:
            return False
        if self._settings.kite_mcp_read_only and tool_name in TRADING_TOOL_NAMES:
            return False
        return True

    def assert_enabled(self) -> None:
        if not self.enabled:
            raise KiteNotEnabledError("Kite Connect is not enabled.")

    def assert_tool_allowed(self, tool_name: str) -> None:
        self.assert_enabled()
        if not self.is_tool_allowed(tool_name):
            raise KiteBlockedToolError(
                f"Kite tool '{tool_name}' is blocked in read-only mode."
            )

    async def aclose(self) -> None:
        if self._owns_client and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    async def _post_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = await self._get_client()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        try:
            response = await client.post(self._settings.kite_mcp_url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise KiteServiceError(f"Kite MCP request failed: {exc}") from exc

        if response.status_code >= 400:
            raise KiteServiceError(
                f"Kite MCP HTTP {response.status_code}: {response.text[:300]}"
            )

        session_header = response.headers.get("Mcp-Session-Id")
        if session_header:
            self._session_id = session_header

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse_json(response.text)

        if not response.content:
            return {}

        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise KiteServiceError("Kite MCP returned invalid JSON") from exc

        if isinstance(body, list):
            for item in body:
                if isinstance(item, dict) and "result" in item:
                    return item
                if isinstance(item, dict) and "error" in item:
                    return item
            return body[0] if body else {}

        return body

    @staticmethod
    def _parse_sse_json(text: str) -> dict[str, Any]:
        for line in text.splitlines():
            if line.startswith("data:"):
                raw = line[5:].strip()
                if raw:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        return parsed
        raise KiteServiceError("Kite MCP SSE response did not contain JSON data")

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
            raise KiteServiceError(self._format_rpc_error(result["error"]))

        if not self._session_id:
            self._session_id = str(uuid.uuid4())

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
            raise KiteServiceError(self._format_rpc_error(result["error"]))

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
            raise KiteServiceError(self._format_rpc_error(result["error"]))

        return self._extract_tool_result(result.get("result", {}))

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
