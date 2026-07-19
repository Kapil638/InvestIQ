"""Immutable shared context for all downstream reasoning stages."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.financial import FinancialResearchResponse
from app.schemas.news import NewsResearchResponse
from app.schemas.research import GuardrailResult


class ResearchContext(BaseModel):
    """
    Single source of truth passed to Analysis, Risk, and Recommendation agents.

    Downstream agents must not fetch external data – only consume this object.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str
    company_name: str | None = None
    financial_data: FinancialResearchResponse | None = None
    news_data: NewsResearchResponse | None = None
    financial_summary: str = ""
    news_summary: str = ""
    data_snapshot_hash: str = ""
    latest_price: float | None = None
    valuation_metrics: dict[str, float | None] = Field(default_factory=dict)
    market_sentiment: str | None = None
    previous_reports_summary: str | None = None
    chroma_context: str | None = None
    supabase_context: str | None = None
    portfolio_context: str | None = None
    guardrails: GuardrailResult | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_agent_prompt_block(self) -> str:
        """Serialize context for CrewAI task inputs."""
        parts = [
            f"TICKER: {self.ticker}",
            f"COMPANY: {self.company_name or self.ticker}",
            f"DATA_SNAPSHOT_HASH: {self.data_snapshot_hash}",
            f"FINANCIAL_SUMMARY:\n{self.financial_summary}",
            f"NEWS_SUMMARY:\n{self.news_summary}",
        ]
        if self.market_sentiment:
            parts.append(f"MARKET_SENTIMENT: {self.market_sentiment}")
        if self.latest_price is not None:
            parts.append(f"LATEST_PRICE: {self.latest_price}")
        if self.valuation_metrics:
            parts.append(f"VALUATION_METRICS: {self.valuation_metrics}")
        if self.previous_reports_summary:
            parts.append(f"PRIOR_REPORTS:\n{self.previous_reports_summary}")
        if self.chroma_context:
            parts.append(f"INSTITUTIONAL_MEMORY:\n{self.chroma_context}")
        if self.portfolio_context:
            parts.append(f"PORTFOLIO_CONTEXT:\n{self.portfolio_context}")
        return "\n\n".join(parts)
