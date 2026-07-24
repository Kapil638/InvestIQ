"""News research service – Agent 2 data layer (no AI opinions)."""

import asyncio
import re

from app.schemas.news import NewsArticle, NewsResearchResponse
from app.services.advisor_utils import bare_symbol
from app.services.tavily_client import TavilyClient
from app.utils.exceptions import ExternalServiceError, InvestIQError
from app.utils.logging import get_logger

logger = get_logger(__name__)

_NAME_STOPWORDS = frozenset(
    {"ltd", "limited", "pvt", "private", "inc", "corp", "corporation", "company", "co", "the", "and"}
)


class NewsResearchService:
    """Collects qualitative news context for a ticker via Tavily."""

    def __init__(self, tavily_client: TavilyClient) -> None:
        self._tavily = tavily_client

    async def collect(self, ticker: str, company_name: str | None = None) -> NewsResearchResponse:
        symbol = ticker.strip().upper()
        bare = bare_symbol(symbol)
        # Prefer the resolved company name as the search anchor — a bare exchange
        # ticker like "RELAXO.NS" carries almost no signal for Tavily's text search
        # and otherwise falls back to generic trending finance headlines.
        label = company_name or bare

        queries = {
            "latest_news": f"{label} ({bare}) latest news",
            "earnings_and_filings": f"{label} quarterly results earnings regulatory filing investor relations",
            "sector_news": f"{label} industry outlook market sentiment",
        }

        results = await asyncio.gather(
            self._tavily.search(queries["latest_news"]),
            self._tavily.search(queries["earnings_and_filings"], max_results=6),
            self._tavily.search(queries["sector_news"], max_results=6),
            return_exceptions=True,
        )

        latest_raw, earnings_raw, sector_raw = results
        warnings: list[str] = []
        keywords = _relevance_keywords(company_name, bare)

        latest_news = _map_results(latest_raw, "latest news", warnings, keywords)
        earnings_and_filings = _map_results(earnings_raw, "earnings and filings", warnings, keywords)
        sector_news = _map_results(sector_raw, "sector news", warnings, keywords)

        return NewsResearchResponse(
            ticker=symbol,
            company_name=company_name,
            latest_news=latest_news,
            earnings_and_filings=earnings_and_filings,
            sector_news=sector_news,
            data_sources=["tavily"],
            warnings=warnings,
        )


def _relevance_keywords(company_name: str | None, bare_ticker: str) -> list[str]:
    """Significant name/ticker tokens an article must mention to count as on-topic."""
    keywords = {bare_ticker.lower()}
    if company_name:
        for word in re.findall(r"[a-zA-Z]+", company_name.lower()):
            if len(word) > 2 and word not in _NAME_STOPWORDS:
                keywords.add(word)
    return list(keywords)


def _is_relevant(article: NewsArticle, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{article.title} {article.snippet or ''}".lower()
    return any(keyword in haystack for keyword in keywords)


def _map_results(
    raw: object,
    label: str,
    warnings: list[str],
    keywords: list[str],
) -> list[NewsArticle]:
    if isinstance(raw, Exception):
        message = str(raw) if isinstance(raw, InvestIQError) else f"Tavily {label} failed"
        warnings.append(message)
        logger.warning("News collection warning (%s): %s", label, message)
        return []

    articles: list[NewsArticle] = []
    dropped = 0
    for item in raw:
        article = NewsArticle(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("content") or item.get("snippet"),
            published_date=item.get("published_date"),
            source=item.get("source"),
        )
        if _is_relevant(article, keywords):
            articles.append(article)
        else:
            dropped += 1

    if dropped:
        logger.info("Filtered %d off-topic %s article(s) as irrelevant", dropped, label)

    return articles
