from unittest.mock import AsyncMock

import pytest

from app.services.news_research_service import NewsResearchService


@pytest.mark.asyncio
async def test_news_service_collects_articles() -> None:
    mock_tavily = AsyncMock()
    mock_tavily.search.side_effect = [
        [{"title": "Apple unveils new iPhone", "url": "https://a.com", "content": "Apple snippet"}],
        [{"title": "Apple Q1 earnings beat", "url": "https://b.com", "content": "AAPL earnings"}],
        [{"title": "Smartphone sector outlook", "url": "https://c.com", "content": "Apple leads sector"}],
    ]

    service = NewsResearchService(tavily_client=mock_tavily)
    result = await service.collect("AAPL", "Apple Inc.")

    assert result.ticker == "AAPL"
    assert len(result.latest_news) == 1
    assert len(result.earnings_and_filings) == 1
    assert len(result.sector_news) == 1
    assert mock_tavily.search.await_count == 3


@pytest.mark.asyncio
async def test_news_service_filters_unrelated_articles() -> None:
    mock_tavily = AsyncMock()
    mock_tavily.search.side_effect = [
        [
            {"title": "Relaxo Footwears Q1 net profit rises", "url": "https://a.com", "content": "Relaxo"},
            {"title": "Reliance Industrial Infrastructure Q1 net profit declines", "url": "https://b.com", "content": "unrelated"},
        ],
        [{"title": "Bulgaria's BrightCap invests in US-based startup", "url": "https://c.com", "content": "unrelated"}],
        [{"title": "Gränges (OM:GRNG) Is Up 6.2%", "url": "https://d.com", "content": "unrelated"}],
    ]

    service = NewsResearchService(tavily_client=mock_tavily)
    result = await service.collect("RELAXO.NS", "Relaxo Footwears Limited")

    assert len(result.latest_news) == 1
    assert result.latest_news[0].title == "Relaxo Footwears Q1 net profit rises"
    assert result.earnings_and_filings == []
    assert result.sector_news == []
