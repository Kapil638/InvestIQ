import json

from app.schemas.financial import (
    CompanyProfile,
    DataCollectionWarning,
    FinancialResearchResponse,
    IncomeStatement,
)
from app.schemas.news import NewsArticle, NewsResearchResponse
from app.services.research_formatters import format_financial_summary, format_news_summary


def _financial_data() -> FinancialResearchResponse:
    return FinancialResearchResponse(
        ticker="RELAXO.NS",
        profile=CompanyProfile(symbol="RELAXO", company_name="Relaxo Footwears Limited"),
        income_statements=[
            IncomeStatement(date="2026-03-31", revenue=1.0),
            IncomeStatement(date="2025-03-31", revenue=2.0),
            IncomeStatement(date="2024-03-31", revenue=3.0),
            IncomeStatement(date="2023-03-31", revenue=4.0),
        ],
        warnings=[DataCollectionWarning(source="yahoo", message="stale data")],
    )


def _news_data() -> NewsResearchResponse:
    articles = [
        NewsArticle(title=f"Headline {i}", url=f"https://example.com/{i}", snippet="body text " * 20)
        for i in range(5)
    ]
    return NewsResearchResponse(ticker="RELAXO", latest_news=articles)


def test_format_financial_summary_full_keeps_history_and_warnings() -> None:
    block = json.loads(format_financial_summary(_financial_data()))
    assert len(block["income_statements"]) == 4
    assert block["warnings"] == ["stale data"]


def test_format_financial_summary_compact_trims_history_and_warnings() -> None:
    block = json.loads(format_financial_summary(_financial_data(), compact=True))
    assert len(block["income_statements"]) == 1
    assert block["income_statements"][0]["date"] == "2026-03-31"
    assert block["warnings"] == []


def test_format_news_summary_full_includes_snippets() -> None:
    block = json.loads(format_news_summary(_news_data()))
    assert len(block["latest_news"]) == 5
    assert "snippet" in block["latest_news"][0]


def test_format_news_summary_compact_drops_snippets_and_limits_articles() -> None:
    block = json.loads(format_news_summary(_news_data(), compact=True))
    assert len(block["latest_news"]) == 3
    assert "snippet" not in block["latest_news"][0]
    assert block["latest_news"][0]["title"] == "Headline 0"
