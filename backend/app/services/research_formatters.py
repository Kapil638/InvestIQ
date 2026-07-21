"""Format pre-collected research data for agent prompts (no re-fetch)."""

from __future__ import annotations

import json

from app.schemas.financial import FinancialResearchResponse
from app.schemas.news import NewsResearchResponse


def format_financial_summary(data: FinancialResearchResponse, *, compact: bool = False) -> str:
    """Compact financial facts for analysis agents – avoids CrewAI tool re-fetch.

    compact=True drops older historical periods and warnings for the Risk/
    Recommendation stages, which already receive the Analysis narrative built
    from the full data - they need current facts for grounding, not the full
    multi-year history again. Numbers, dates, and ratios stay intact so
    guardrail fact-checking (built independently from the raw data, not from
    this string) is unaffected.
    """
    profile = data.profile
    periods = 1 if compact else 4
    block = {
        "ticker": data.ticker,
        "company_name": profile.company_name,
        "sector": profile.sector,
        "industry": profile.industry,
        "market_cap": profile.market_cap,
        "price": profile.price,
        "data_sources": data.data_sources,
        "income_statements": [s.model_dump() for s in data.income_statements[:periods]],
        "balance_sheets": [s.model_dump() for s in data.balance_sheets[:periods]],
        "cash_flow_statements": [s.model_dump() for s in data.cash_flow_statements[:periods]],
        "ratios": [r.model_dump() for r in data.ratios[:4]],
        "key_metrics": [m.model_dump() for m in data.key_metrics[:4]],
        "market_data": data.market_data.model_dump() if data.market_data else None,
        "warnings": [] if compact else [w.message for w in data.warnings],
    }
    return json.dumps(block, indent=2, default=str)


def format_news_summary(data: NewsResearchResponse, *, compact: bool = False) -> str:
    """Compact news context for analysis agents – avoids duplicate Tavily calls.

    compact=True keeps titles/sources/dates (the facts guardrails and the
    agent's own citations rely on) but drops the verbose snippet body text,
    for the Risk/Recommendation stages which already have the Analysis
    narrative's synthesis of these same articles.
    """

    def _articles(items: list, limit: int, include_snippet: bool) -> list[dict]:
        articles = []
        for a in items[:limit]:
            entry: dict = {
                "title": a.title,
                "source": a.source,
                "published_date": a.published_date,
            }
            if include_snippet:
                entry["snippet"] = (a.snippet or "")[:280]
            articles.append(entry)
        return articles

    limit = 3 if compact else 5
    block = {
        "ticker": data.ticker,
        "company_name": data.company_name,
        "latest_news": _articles(data.latest_news, limit, include_snippet=not compact),
        "earnings_and_filings": _articles(data.earnings_and_filings, limit, include_snippet=not compact),
        "sector_news": _articles(data.sector_news, limit, include_snippet=not compact),
        "warnings": [] if compact else data.warnings,
    }
    return json.dumps(block, indent=2, default=str)
