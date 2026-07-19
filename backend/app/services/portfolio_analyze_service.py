"""Portfolio-level AI analysis – single OpenRouter LLM call, no CrewAI."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.agents.llm import build_llm
from app.core.config import Settings
from app.schemas.portfolio import (
    PortfolioAnalyzeRequest,
    PortfolioAnalyzeResponse,
    SectorExposureItem,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

_ANALYZE_SYSTEM = """You are InvestIQ, an AI equity research assistant for Indian portfolios.

Analyze the user's Zerodha portfolio holdings for research purposes only.
- Output valid JSON matching the required schema exactly.
- Use research wording: "research suggestion", "worth monitoring", "consider reviewing".
- Do NOT instruct the user to place, modify, or cancel orders.
- Do NOT say "execute buy/sell" or "place order".
- Base concentration and sector views on the supplied holdings data.
- If data is missing, note it rather than inventing numbers.
"""


class PortfolioAnalyzeService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def analyze(self, request: PortfolioAnalyzeRequest) -> PortfolioAnalyzeResponse:
        holdings_payload = [h.model_dump(exclude_none=True) for h in request.holdings]
        prompt = (
            f"{_ANALYZE_SYSTEM}\n\n"
            f"HOLDINGS:\n{json.dumps(holdings_payload, indent=2)}\n\n"
            "Return JSON with keys: summary, concentration_risk, strong_holdings (array of strings), "
            "weak_holdings (array), sector_exposure (array of {sector, allocation_percent, holdings}), "
            "rebalance_suggestions (array), three_year_view, watchlist_actions (array).\n"
            "JSON:"
        )

        llm = await asyncio.to_thread(build_llm, self._settings)
        raw = await asyncio.to_thread(_call_llm, llm, prompt)
        return _parse_response(raw)


def _call_llm(llm: Any, prompt: str) -> str:
    result = llm.call(prompt)
    if isinstance(result, str):
        return result
    return str(result)


def _parse_response(raw: str) -> PortfolioAnalyzeResponse:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return PortfolioAnalyzeResponse(
            summary=text[:2000],
            concentration_risk="Not available in this analysis.",
            three_year_view="Not available in this analysis.",
        )

    sector_items = []
    for item in data.get("sector_exposure") or []:
        if isinstance(item, dict):
            sector_items.append(
                SectorExposureItem(
                    sector=str(item.get("sector", "Unknown")),
                    allocation_percent=float(item.get("allocation_percent", 0)),
                    holdings=[str(h) for h in item.get("holdings", [])],
                )
            )

    return PortfolioAnalyzeResponse(
        summary=str(data.get("summary", "")),
        concentration_risk=str(data.get("concentration_risk", "")),
        strong_holdings=[str(x) for x in data.get("strong_holdings", [])],
        weak_holdings=[str(x) for x in data.get("weak_holdings", [])],
        sector_exposure=sector_items,
        rebalance_suggestions=[str(x) for x in data.get("rebalance_suggestions", [])],
        three_year_view=str(data.get("three_year_view", "")),
        watchlist_actions=[str(x) for x in data.get("watchlist_actions", [])],
    )
