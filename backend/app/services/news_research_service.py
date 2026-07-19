"""News research service – Agent 2 data layer (no AI opinions)."""

import asyncio

from app.schemas.news import NewsArticle, NewsResearchResponse
from app.services.tavily_client import TavilyClient
from app.utils.exceptions import ExternalServiceError, InvestIQError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class NewsResearchService:
    """Collects qualitative news context for a ticker via Tavily."""

    def __init__(self, tavily_client: TavilyClient) -> None:
        self._tavily = tavily_client

    async def collect(self, ticker: str, company_name: str | None = None) -> NewsResearchResponse:
        symbol = ticker.strip().upper()
        label = company_name or symbol

        queries = {
            "latest_news": f"{label} {symbol} latest news stock",
            "earnings_and_filings": f"{label} earnings report SEC filing investor relations",
            "sector_news": f"{label} sector industry outlook market sentiment",
        }

        results = await asyncio.gather(
            self._tavily.search(queries["latest_news"]),
            self._tavily.search(queries["earnings_and_filings"], max_results=6),
            self._tavily.search(queries["sector_news"], max_results=6),
            return_exceptions=True,
        )

        latest_raw, earnings_raw, sector_raw = results
        warnings: list[str] = []

        latest_news = _map_results(latest_raw, "latest news", warnings)
        earnings_and_filings = _map_results(earnings_raw, "earnings and filings", warnings)
        sector_news = _map_results(sector_raw, "sector news", warnings)

        return NewsResearchResponse(
            ticker=symbol,
            company_name=company_name,
            latest_news=latest_news,
            earnings_and_filings=earnings_and_filings,
            sector_news=sector_news,
            data_sources=["tavily"],
            warnings=warnings,
        )


def _map_results(
    raw: object,
    label: str,
    warnings: list[str],
) -> list[NewsArticle]:
    if isinstance(raw, Exception):
        message = str(raw) if isinstance(raw, InvestIQError) else f"Tavily {label} failed"
        warnings.append(message)
        logger.warning("News collection warning (%s): %s", label, message)
        return []

    articles: list[NewsArticle] = []
    for item in raw:
        articles.append(
            NewsArticle(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content") or item.get("snippet"),
                published_date=item.get("published_date"),
                source=item.get("source"),
            )
        )
    return articles
