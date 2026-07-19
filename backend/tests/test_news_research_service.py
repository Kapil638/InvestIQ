from unittest.mock import AsyncMock

import pytest

from app.services.news_research_service import NewsResearchService


@pytest.mark.asyncio
async def test_news_service_collects_articles() -> None:
    mock_tavily = AsyncMock()
    mock_tavily.search.side_effect = [
        [{"title": "Latest", "url": "https://a.com", "content": "snippet"}],
        [{"title": "Earnings", "url": "https://b.com", "content": "earnings"}],
        [{"title": "Sector", "url": "https://c.com", "content": "sector"}],
    ]

    service = NewsResearchService(tavily_client=mock_tavily)
    result = await service.collect("AAPL", "Apple Inc.")

    assert result.ticker == "AAPL"
    assert len(result.latest_news) == 1
    assert len(result.earnings_and_filings) == 1
    assert len(result.sector_news) == 1
    assert mock_tavily.search.await_count == 3
