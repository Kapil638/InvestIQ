"""Fast follow-up chat on a saved research report – single LLM call, no CrewAI pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import re

from app.agents.llm import build_llm
from app.core.config import Settings
from app.llm.caller import call_llm_with_retry
from app.schemas.chat import ChatTurn, ReportChatResponse
from app.services.rag_service import RagService
from app.services.report_context import (
    build_previous_reports_context,
    build_report_context,
)
from app.services.report_storage_service import ReportStorageService
from app.utils.exceptions import ReportNotFoundError
from app.utils.logging import get_logger
from app.utils import ttl_cache
from app.utils.timing import async_timed_operation

logger = get_logger(__name__)

_CHAT_SYSTEM = """You are InvestIQ, an AI equity research assistant for Indian listed stocks.

Answer follow-up questions using the provided report context only.
- Be structured and concise (120–350 words).
- Do NOT instruct the user to place, modify, or cancel orders.
- If information is missing, say "Not available in this report."
- Research/analysis only — not trade execution advice.
"""

_CHANGE_PATTERNS = re.compile(
    r"what changed|since (my |the )?last report|compared to (my )?previous|vs last report",
    re.IGNORECASE,
)


class ReportChatService:
    """Answer questions about a specific saved report."""

    def __init__(
        self,
        settings: Settings,
        storage: ReportStorageService,
        rag_service: RagService | None = None,
    ) -> None:
        self._settings = settings
        self._storage = storage
        self._rag = rag_service

    async def chat(
        self,
        report_id: str,
        question: str,
        history: list[ChatTurn] | None = None,
    ) -> ReportChatResponse:
        cleaned = question.strip()
        prior_turns = (history or [])[-10:]

        async with async_timed_operation("report_chat", report_id=report_id):
            stored = await self._storage.get(report_id)
            if not stored:
                raise ReportNotFoundError(f"Report not found: {report_id}")

            context_blocks, sources = await self._build_context_blocks(
                report_id, stored, cleaned
            )

            llm = await asyncio.to_thread(
                lambda: build_llm(self._settings, skip_probe=True)
            )
            history_block = _format_history(prior_turns)
            prompt = (
                f"{_CHAT_SYSTEM}\n\n"
                + "\n\n".join(context_blocks)
                + (f"\n\n{history_block}" if history_block else "")
                + f"USER QUESTION:\n{cleaned}\n\nANSWER:"
            )

            logger.info("Report chat %s: %s", report_id, cleaned[:80])
            answer = await asyncio.to_thread(
                call_llm_with_retry,
                llm,
                prompt,
                settings=self._settings,
                label="report_chat",
            )

        return ReportChatResponse(
            answer=answer.strip(),
            sources=sources,
            report_id=report_id,
        )

    async def _build_context_blocks(
        self, report_id: str, stored, question: str
    ) -> tuple[list[str], list[str]]:
        context_blocks, sources = await self._get_cached_report_context(
            report_id, stored
        )

        rag_block = await self._get_rag_context_block(report_id, stored, question)
        if rag_block:
            context_blocks = [*context_blocks, rag_block]
            sources = [*sources, "ChromaDB"]

        return context_blocks, sources

    async def _get_cached_report_context(
        self, report_id: str, stored
    ) -> tuple[list[str], list[str]]:
        cache_key = f"{report_id}"
        cached = ttl_cache.get("chat_context", cache_key)
        if cached is not None:
            return cached

        context_blocks = [f"CURRENT REPORT:\n{build_report_context(stored)}"]

        prior_summaries, _ = await self._storage.list_reports(
            ticker=stored.ticker, limit=6, offset=0
        )
        prior_context = build_previous_reports_context(
            prior_summaries, exclude_id=report_id, limit=4
        )
        if prior_context:
            context_blocks.append(prior_context)

        sources = ["Stored report", "OpenRouter LLM"]
        if prior_context:
            sources.append("Report history")

        result = (context_blocks, sources)
        ttl_cache.set("chat_context", cache_key, result)
        return result

    async def _get_rag_context_block(
        self, report_id: str, stored, question: str
    ) -> str | None:
        if not self._rag or not self._rag.is_enabled:
            return None

        cache_key = (
            f"{report_id}:"
            f"{hashlib.sha256(question.lower().encode()).hexdigest()[:12]}"
        )
        cached = ttl_cache.get("chat_context", cache_key)
        if cached is not None:
            return cached

        rag_snippets: list[str] = []
        try:
            similar = await self._rag.search_similar(
                question, ticker=stored.ticker, limit=3
            )
            for match in similar.results:
                if match.report_id != report_id:
                    rag_snippets.append(
                        f"[{match.report_id}] relevance={match.relevance_score}: {match.snippet}"
                    )
        except Exception as exc:
            logger.debug("RAG skipped for report chat %s: %s", report_id, exc)
            return None

        if not rag_snippets:
            return None

        rag_block = "SIMILAR PAST RESEARCH SNIPPETS:\n" + "\n".join(rag_snippets)
        ttl_cache.set("chat_context", cache_key, rag_block)
        return rag_block


def _format_history(history: list[ChatTurn]) -> str:
    if not history:
        return ""
    lines: list[str] = []
    for turn in history:
        label = "User" if turn.role == "user" else "Assistant"
        lines.append(f"{label}: {turn.content}")
    return "PRIOR CONVERSATION:\n" + "\n".join(lines) + "\n\n"
