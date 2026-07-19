"""Targeted research Q&A – single LLM call with financial + news context."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.agents.llm import build_llm
from app.core.config import Settings
from app.llm.caller import call_llm_with_retry
from app.schemas.ask import ResearchAskResponse
from app.schemas.financial import CompanyProfile, FinancialSummaryResponse
from app.services.financial_data_service import FinancialDataService
from app.services.tavily_client import TavilyClient
from app.utils.logging import get_logger

logger = get_logger(__name__)

_ASK_SYSTEM = """You are InvestIQ, an AI research assistant for Indian listed equities (NSE/BSE).

Answer the user's specific question using ONLY the provided context.
- Be direct, structured, and concise (roughly 150–400 words unless a table is requested).
- Cite facts from context; do not invent numbers or events not present in context.
- If context is insufficient, state what is missing instead of guessing.
- Do NOT produce a full institutional Buy/Hold/Avoid report unless explicitly asked.
- Use INR for Indian stocks when discussing money.
"""


class ResearchAskService:
    """Answer a focused research question without running the full agent pipeline."""

    def __init__(self, settings: Settings, financial_service: FinancialDataService) -> None:
        self._settings = settings
        self._financial_service = financial_service

    async def ask(self, ticker: str, question: str) -> ResearchAskResponse:
        symbol = ticker.strip().upper()
        cleaned_question = question.strip()

        summary, profile, news_snippets = await self._gather_context(symbol, cleaned_question)
        context = self._build_context(summary, profile, news_snippets)

        llm = await asyncio.to_thread(lambda: build_llm(self._settings, skip_probe=True))
        prompt = (
            f"{_ASK_SYSTEM}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"USER QUESTION:\n{cleaned_question}\n\n"
            "ANSWER:"
        )

        logger.info("Research ask for %s: %s", symbol, cleaned_question[:80])
        answer = await asyncio.to_thread(
            call_llm_with_retry,
            llm,
            prompt,
            settings=self._settings,
            label="research_ask",
        )

        sources = [summary.data_source, "OpenRouter LLM"]
        if news_snippets:
            sources.append("Tavily")

        return ResearchAskResponse(
            ticker=summary.ticker,
            company_name=summary.company_name or profile.company_name,
            question=cleaned_question,
            answer=answer.strip(),
            data_sources=sources,
        )

    async def _gather_context(
        self, symbol: str, question: str
    ) -> tuple[FinancialSummaryResponse, CompanyProfile, list[dict[str, str]]]:
        summary = await self._financial_service.get_summary(symbol)
        profile = CompanyProfile(
            symbol=summary.ticker,
            company_name=summary.company_name,
            sector=summary.sector,
            industry=summary.industry,
            market_cap=summary.market_cap,
            price=summary.current_price,
        )
        news_snippets = await self._fetch_news_snippets(
            symbol, profile.company_name or symbol, question
        )
        return summary, profile, news_snippets

    async def _fetch_news_snippets(
        self, symbol: str, company_name: str, question: str
    ) -> list[dict[str, str]]:
        if not self._settings.tavily_api_key:
            return []

        query = f"{company_name} {symbol} India stock {question}"
        client = TavilyClient(api_key=self._settings.tavily_api_key)

        try:
            results = await client.search(query, max_results=5)
        except Exception as exc:
            logger.warning("Tavily search skipped for ask %s: %s", symbol, exc)
            return []

        snippets: list[dict[str, str]] = []
        for item in results[:5]:
            snippets.append(
                {
                    "title": str(item.get("title", "")),
                    "snippet": str(item.get("content") or item.get("snippet") or "")[:500],
                    "source": str(item.get("source", "")),
                }
            )
        return snippets

    def _build_context(
        self,
        summary: FinancialSummaryResponse,
        profile: CompanyProfile,
        news_snippets: list[dict[str, str]],
    ) -> str:
        financial_block = {
            "ticker": summary.ticker,
            "company_name": summary.company_name or profile.company_name,
            "sector": summary.sector or profile.sector,
            "industry": summary.industry or profile.industry,
            "description": profile.description,
            "market_cap": summary.market_cap,
            "current_price": summary.current_price,
            "currency": summary.currency,
            "pe_ratio": summary.pe_ratio,
            "pb_ratio": summary.pb_ratio,
            "roe": summary.roe,
            "debt_to_equity": summary.debt_to_equity,
            "revenue_growth": summary.revenue_growth,
            "profit_margin": summary.profit_margin,
            "dividend_yield": summary.dividend_yield,
        }

        parts = ["FINANCIAL SNAPSHOT:\n" + json.dumps(financial_block, indent=2, default=str)]

        if news_snippets:
            parts.append("RECENT NEWS SNIPPETS:\n" + json.dumps(news_snippets, indent=2))

        return "\n\n".join(parts)

