"""Format pre-collected research data for agent prompts (no re-fetch)."""

from __future__ import annotations

import json

from app.schemas.financial import FinancialResearchResponse
from app.schemas.news import NewsResearchResponse


def format_financial_summary(data: FinancialResearchResponse) -> str:
    """Compact financial facts for analysis agents – avoids CrewAI tool re-fetch."""
    profile = data.profile
    block = {
        "ticker": data.ticker,
        "company_name": profile.company_name,
        "sector": profile.sector,
        "industry": profile.industry,
        "market_cap": profile.market_cap,
        "price": profile.price,
        "data_sources": data.data_sources,
        "income_statements": [s.model_dump() for s in data.income_statements[:4]],
        "balance_sheets": [s.model_dump() for s in data.balance_sheets[:4]],
        "cash_flow_statements": [s.model_dump() for s in data.cash_flow_statements[:4]],
        "ratios": [r.model_dump() for r in data.ratios[:4]],
        "key_metrics": [m.model_dump() for m in data.key_metrics[:4]],
        "market_data": data.market_data.model_dump() if data.market_data else None,
        "warnings": [w.message for w in data.warnings],
    }
    return json.dumps(block, indent=2, default=str)


def format_news_summary(data: NewsResearchResponse) -> str:
    """Compact news context for analysis agents – avoids duplicate Tavily calls."""

    def _articles(items: list, limit: int = 5) -> list[dict]:
        return [
            {
                "title": a.title,
                "source": a.source,
                "snippet": (a.snippet or "")[:280],
                "published_date": a.published_date,
            }
            for a in items[:limit]
        ]

    block = {
        "ticker": data.ticker,
        "company_name": data.company_name,
        "latest_news": _articles(data.latest_news),
        "earnings_and_filings": _articles(data.earnings_and_filings),
        "sector_news": _articles(data.sector_news),
        "warnings": data.warnings,
    }
    return json.dumps(block, indent=2, default=str)
