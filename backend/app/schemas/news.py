"""Pydantic models for news research data (Agent 2 output)."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    title: str
    url: str
    snippet: str | None = None
    published_date: str | None = None
    source: str | None = None


class NewsResearchResponse(BaseModel):
    """Structured output from Agent 2 – qualitative context, no recommendations."""

    ticker: str
    company_name: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    latest_news: list[NewsArticle] = Field(default_factory=list)
    earnings_and_filings: list[NewsArticle] = Field(default_factory=list)
    sector_news: list[NewsArticle] = Field(default_factory=list)
    sentiment_summary: str | None = None
    data_sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
