"""Portfolio-level AI analysis - real fundamentals + deterministic concentration
metrics feeding a single OpenRouter LLM call, no CrewAI.

Previously this sent the LLM nothing but the raw Kite holdings (symbol, qty,
price, P&L - no sector, no fundamentals), so "sector exposure" and
"rebalance suggestions" were the model guessing/inventing facts about these
tickers from training data rather than reasoning over real, current numbers.
Sector allocation and concentration risk are now computed deterministically
in Python from real per-holding fundamentals (same Yahoo/Tapetide pipeline
the rest of the app uses), matching the "deterministic scoring + LLM
narrative" pattern already used for single-ticker research reports.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from app.agents.llm import build_llm
from app.core.config import Settings
from app.schemas.financial import FinancialSummaryResponse
from app.schemas.portfolio import (
    PortfolioAnalyzeHoldingInput,
    PortfolioAnalyzeRequest,
    PortfolioAnalyzeResponse,
    SectorExposureItem,
)
from app.services.financial_data_service import FinancialDataService
from app.utils.logging import get_logger

logger = get_logger(__name__)

_ANALYZE_SYSTEM = """You are InvestIQ, an AI equity research assistant for Indian portfolios.

Analyze the user's Zerodha portfolio for research purposes only.
- Output valid JSON matching the required schema exactly.
- Use research wording: "research suggestion", "worth monitoring", "consider reviewing".
- Do NOT instruct the user to place, modify, or cancel orders.
- Do NOT say "execute buy/sell" or "place order".
- CONFIRMED_FACTS below are computed directly from the portfolio's real
  fundamentals - treat every number in it as ground truth. Do not
  contradict, re-derive, or invent different sector/allocation/ratio
  numbers than what CONFIRMED_FACTS states.
- Where a holding's fundamentals are marked "not available", say so rather
  than inventing a number.
"""

_MAX_CONCURRENT_ENRICHMENTS = 6

# Standard portfolio-concentration thresholds (not InvestIQ-specific
# invention): >40% in one sector or >20% in one stock is conventionally
# flagged as concentrated; HHI bands below follow the same convention used
# for market-concentration analysis generally.
_SECTOR_CONCENTRATION_THRESHOLD = 40.0
_SINGLE_STOCK_CONCENTRATION_THRESHOLD = 20.0
_HIGH_PE_THRESHOLD = 60.0
_HIGH_DEBT_TO_EQUITY_THRESHOLD = 150.0
_LOW_ROE_THRESHOLD = 5.0
_MIN_SECTORS_FOR_DIVERSIFICATION = 3


@dataclass
class _EnrichedHolding:
    holding: PortfolioAnalyzeHoldingInput
    summary: FinancialSummaryResponse | None


@dataclass
class _ConcentrationMetrics:
    total_value: float
    sector_exposure: list[SectorExposureItem]
    hhi: float
    hhi_band: str
    flags: list[str] = field(default_factory=list)


class PortfolioAnalyzeService:
    def __init__(self, settings: Settings, financial_data_service: FinancialDataService) -> None:
        self._settings = settings
        self._financial = financial_data_service

    async def analyze(self, request: PortfolioAnalyzeRequest) -> PortfolioAnalyzeResponse:
        enriched = await self._enrich_holdings(request.holdings)
        metrics = _compute_concentration_metrics(enriched)
        prompt = _build_prompt(enriched, metrics)

        llm = await asyncio.to_thread(build_llm, self._settings)
        raw = await asyncio.to_thread(_call_llm, llm, prompt)
        response = _parse_response(raw)

        # Never trust the LLM's own arithmetic for sector allocation - it's
        # computed deterministically above from real fundamentals.
        response.sector_exposure = metrics.sector_exposure
        # Deterministic, fact-checked flags always lead; whatever the LLM
        # added on top follows, deduplicated.
        response.rebalance_suggestions = metrics.flags + [
            s for s in response.rebalance_suggestions if s not in metrics.flags
        ]
        return response

    async def _enrich_holdings(
        self, holdings: list[PortfolioAnalyzeHoldingInput]
    ) -> list[_EnrichedHolding]:
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_ENRICHMENTS)

        async def _fetch(holding: PortfolioAnalyzeHoldingInput) -> _EnrichedHolding:
            async with semaphore:
                try:
                    summary = await self._financial.get_summary(holding.symbol)
                except Exception as exc:
                    logger.debug(
                        "Portfolio analysis: fundamentals unavailable for %s: %s",
                        holding.symbol,
                        exc,
                    )
                    summary = None
                return _EnrichedHolding(holding=holding, summary=summary)

        return await asyncio.gather(*(_fetch(h) for h in holdings))


def _call_llm(llm: Any, prompt: str) -> str:
    result = llm.call(prompt)
    if isinstance(result, str):
        return result
    return str(result)


def _compute_concentration_metrics(enriched: list[_EnrichedHolding]) -> _ConcentrationMetrics:
    total_value = sum(e.holding.current_value or 0.0 for e in enriched) or 1.0

    sector_totals: dict[str, float] = {}
    sector_holdings: dict[str, list[str]] = {}
    for e in enriched:
        sector = _resolve_sector(e)
        value = e.holding.current_value or 0.0
        sector_totals[sector] = sector_totals.get(sector, 0.0) + value
        sector_holdings.setdefault(sector, []).append(e.holding.symbol)

    sector_exposure = [
        SectorExposureItem(
            sector=sector,
            allocation_percent=round(value / total_value * 100, 2),
            holdings=sector_holdings[sector],
        )
        for sector, value in sorted(sector_totals.items(), key=lambda kv: -kv[1])
    ]

    hhi = sum((v / total_value * 100) ** 2 for v in sector_totals.values())
    if hhi < 1500:
        hhi_band = "well-diversified across sectors"
    elif hhi < 2500:
        hhi_band = "moderately concentrated across sectors"
    else:
        hhi_band = "highly concentrated in a small number of sectors"

    flags: list[str] = []

    if sector_exposure and sector_exposure[0].allocation_percent > _SECTOR_CONCENTRATION_THRESHOLD:
        top = sector_exposure[0]
        flags.append(
            f"Research suggestion: {top.sector} is {top.allocation_percent:.1f}% of the "
            f"portfolio ({', '.join(top.holdings)}), above the {_SECTOR_CONCENTRATION_THRESHOLD:.0f}% "
            "single-sector concentration threshold - worth reviewing exposure here."
        )

    sorted_by_value = sorted(enriched, key=lambda e: -(e.holding.current_value or 0.0))
    if sorted_by_value:
        top_holding = sorted_by_value[0]
        top_pct = (top_holding.holding.current_value or 0.0) / total_value * 100
        if top_pct > _SINGLE_STOCK_CONCENTRATION_THRESHOLD:
            flags.append(
                f"Research suggestion: {top_holding.holding.symbol} alone is {top_pct:.1f}% of the "
                f"portfolio, above the {_SINGLE_STOCK_CONCENTRATION_THRESHOLD:.0f}% single-stock "
                "concentration threshold."
            )

    if len(sector_totals) < _MIN_SECTORS_FOR_DIVERSIFICATION and len(enriched) >= 4:
        flags.append(
            f"Research suggestion: holdings span only {len(sector_totals)} sector(s) - "
            "worth monitoring diversification across a broader set of sectors."
        )

    for e in enriched:
        s = e.summary
        if s is None:
            continue
        if s.pe_ratio is not None and s.pe_ratio > _HIGH_PE_THRESHOLD and (
            e.holding.pnl_percent is not None and e.holding.pnl_percent < -10
        ):
            flags.append(
                f"Research suggestion: {e.holding.symbol} trades at a P/E of {s.pe_ratio:.1f}x "
                f"while down {e.holding.pnl_percent:.1f}% - worth evaluating whether the "
                "premium valuation is still supported by fundamentals."
            )
        if s.debt_to_equity is not None and s.debt_to_equity > _HIGH_DEBT_TO_EQUITY_THRESHOLD:
            flags.append(
                f"Research suggestion: {e.holding.symbol} carries a debt-to-equity ratio of "
                f"{s.debt_to_equity:.1f}%, above the {_HIGH_DEBT_TO_EQUITY_THRESHOLD:.0f}% "
                "high-leverage threshold - worth monitoring balance sheet risk."
            )
        roe_percent = _as_percent(s.roe)
        if roe_percent is not None and 0 <= roe_percent < _LOW_ROE_THRESHOLD:
            flags.append(
                f"Research suggestion: {e.holding.symbol}'s return on equity ({roe_percent:.1f}%) is "
                "below typical benchmarks - worth reviewing capital efficiency versus sector peers."
            )

    return _ConcentrationMetrics(
        total_value=total_value,
        sector_exposure=sector_exposure,
        hhi=round(hhi, 1),
        hhi_band=hhi_band,
        flags=flags,
    )


def _as_percent(value: float | None) -> float | None:
    """ROE/margin/growth ratios arrive as 0-1 fractions from Yahoo Finance
    (e.g. 0.42 for 42%) - unlike debt_to_equity, which is already
    percentage-scale. Comparing/displaying these raw without conversion
    would make virtually every real company look artificially "low" against
    a percentage threshold."""
    if value is None:
        return None
    return value * 100 if abs(value) <= 1 else value


def _resolve_sector(e: _EnrichedHolding) -> str:
    if e.summary and e.summary.sector:
        return e.summary.sector
    if e.holding.sector:
        return e.holding.sector
    return "Unknown"


def _build_prompt(enriched: list[_EnrichedHolding], metrics: _ConcentrationMetrics) -> str:
    holdings_payload = []
    for e in enriched:
        row: dict[str, Any] = e.holding.model_dump(exclude_none=True)
        if e.summary:
            row["sector"] = e.summary.sector or row.get("sector")
            row["industry"] = e.summary.industry or None
            row["pe_ratio"] = e.summary.pe_ratio
            row["pb_ratio"] = e.summary.pb_ratio
            row["roe_percent"] = _as_percent(e.summary.roe)
            row["debt_to_equity_percent"] = e.summary.debt_to_equity  # already percentage-scale
            row["revenue_growth_percent"] = _as_percent(e.summary.revenue_growth)
            row["profit_margin_percent"] = _as_percent(e.summary.profit_margin)
        else:
            row["fundamentals"] = "not available"
        holdings_payload.append(row)

    confirmed_facts = {
        "total_portfolio_value": round(metrics.total_value, 2),
        "sector_exposure": [s.model_dump() for s in metrics.sector_exposure],
        "concentration_hhi": metrics.hhi,
        "concentration_assessment": metrics.hhi_band,
        "computed_rebalance_flags": metrics.flags,
    }

    return (
        f"{_ANALYZE_SYSTEM}\n\n"
        f"HOLDINGS (with real fundamentals where available):\n"
        f"{json.dumps(holdings_payload, indent=2, default=str)}\n\n"
        f"CONFIRMED_FACTS (computed deterministically - do not contradict):\n"
        f"{json.dumps(confirmed_facts, indent=2)}\n\n"
        "Return JSON with keys: summary, concentration_risk, strong_holdings (array of strings), "
        "weak_holdings (array), sector_exposure (array of {sector, allocation_percent, holdings} - "
        "must match CONFIRMED_FACTS.sector_exposure exactly), "
        "rebalance_suggestions (array - CONFIRMED_FACTS.computed_rebalance_flags are already "
        "included separately, so add only additional qualitative suggestions here, grounded in "
        "the real fundamentals shown per holding), three_year_view, watchlist_actions (array).\n"
        "JSON:"
    )


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
