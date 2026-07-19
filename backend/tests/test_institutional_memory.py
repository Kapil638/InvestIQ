"""Tests for institutional memory injection into research context."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.schemas.agent_outputs import AnalysisOutput, AnalysisScores, RiskOutput, RiskScores
from app.schemas.financial import CompanyProfile, FinancialResearchResponse
from app.schemas.news import NewsResearchResponse
from app.schemas.research import (
    InvestmentRecommendation,
    RecommendationRating,
    ResearchReportResponse,
)
from app.schemas.storage import SimilarReportMatch, SimilarReportsResponse
from app.services.rag_service import RagService
from app.services.research_context_builder import build_research_context


def _prior_report() -> ResearchReportResponse:
    return ResearchReportResponse(
        ticker="INFY",
        generated_at=datetime(2026, 7, 1, tzinfo=UTC),
        confidence_score=72,
        analysis="Infosys remains a quality compounder with stable margins and AI services demand.",
        analysis_output=AnalysisOutput(
            narrative="Quality compounder",
            scores=AnalysisScores(
                growth=70,
                profitability=80,
                valuation=55,
                financial_health=78,
                management=75,
                sector_strength=70,
                macro=60,
                overall=72,
            ),
        ),
        risk_output=RiskOutput(
            narrative="Moderate risk",
            scores=RiskScores(
                overall_risk=40,
                financial=30,
                governance=25,
                macro=45,
                business=35,
                valuation=50,
                regulatory=20,
            ),
            risks=["Client concentration", "Wage inflation"],
        ),
        recommendation=InvestmentRecommendation(
            rating=RecommendationRating.HOLD,
            confidence_score=72,
            reasoning="Valuation leaves limited margin of safety despite solid execution.",
            risks=["Client concentration", "FX volatility"],
            target_price_range="1500-1650",
            investment_horizon="12-18 months",
        ),
    )


def test_prior_report_summary_is_rich() -> None:
    fin = FinancialResearchResponse(
        ticker="INFY",
        profile=CompanyProfile(symbol="INFY", company_name="Infosys", price=1550.0),
    )
    news = NewsResearchResponse(ticker="INFY", sentiment_summary="Constructive")
    ctx = build_research_context(
        "INFY",
        fin,
        news,
        previous_report=_prior_report(),
        chroma_context="- [INFY | Hold] Prior thesis emphasized valuation caution.",
    )
    block = ctx.to_agent_prompt_block()
    assert "PRIOR_REPORTS:" in block
    assert "INSTITUTIONAL_MEMORY:" in block
    assert "Rating: Hold" in block
    assert "Prior investment thesis:" in block
    assert "Prior analysis scores:" in block
    assert "valuation caution" in block


@pytest.mark.asyncio
async def test_rag_context_for_ticker_formats_matches() -> None:
    store = AsyncMock()
    store.search_similar = AsyncMock(
        return_value=[
            SimilarReportMatch(
                report_id="r1",
                ticker="INFY",
                snippet="Quality franchise, fair valuation.",
                relevance_score=0.82,
                rating="Hold",
            )
        ]
    )
    # RagService.search_similar wraps vector store — monkeypatch at service level
    rag = RagService(vector_store=object())  # type: ignore[arg-type]
    rag.search_similar = AsyncMock(  # type: ignore[method-assign]
        return_value=SimilarReportsResponse(
            query="q",
            ticker="INFY",
            results=[
                SimilarReportMatch(
                    report_id="r1",
                    ticker="INFY",
                    snippet="Quality franchise, fair valuation.",
                    relevance_score=0.82,
                    rating="Hold",
                )
            ],
        )
    )
    text = await rag.get_context_for_ticker("INFY")
    assert "Semantic institutional memory related to INFY" in text
    assert "Quality franchise" in text
    assert "similarity=0.820" in text


@pytest.mark.asyncio
async def test_crew_run_passes_chroma_into_context(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings
    from app.services.research_crew_service import ResearchCrewService

    settings = Settings(
        yfinance_enabled=True,
        tavily_api_key="tavily-key",
        openrouter_api_key="openrouter-key",
        llm_provider="openrouter",
        crew_verbose=False,
        cache_enabled=False,
    )
    service = ResearchCrewService(settings=settings)

    captured: dict = {}

    async def fake_collect(symbol, tracer, data_sources):
        return (
            FinancialResearchResponse(
                ticker=symbol,
                profile=CompanyProfile(symbol=symbol, company_name="Infosys", price=1500.0),
            ),
            NewsResearchResponse(ticker=symbol),
            False,
            False,
        )

    def fake_build_context(ticker, fin, news, **kwargs):
        captured.update(kwargs)
        return build_research_context(ticker, fin, news, **kwargs)

    rag = RagService(vector_store=object())  # type: ignore[arg-type]
    rag.search_similar = AsyncMock(  # type: ignore[method-assign]
        return_value=SimilarReportsResponse(
            query="q",
            ticker="INFY",
            results=[
                SimilarReportMatch(
                    report_id="r1",
                    ticker="INFY",
                    snippet="Memory snippet",
                    relevance_score=0.9,
                    rating="Buy",
                )
            ],
        )
    )

    # Short-circuit after context is built by raising a sentinel later in run()
    class StopAfterContext(Exception):
        pass

    async def boom(*_a, **_k):
        raise StopAfterContext()

    monkeypatch.setattr(service, "_collect_structured_data_traced", fake_collect)
    monkeypatch.setattr(
        "app.services.research_crew_service.build_research_context",
        fake_build_context,
    )
    monkeypatch.setattr(
        "app.services.research_crew_service.build_llm",
        boom,
    )
    monkeypatch.setattr(
        "app.agents.llm.build_llm",
        lambda *_a, **_k: (_ for _ in ()).throw(StopAfterContext()),
    )

    with pytest.raises(StopAfterContext):
        # build_llm is imported inside run via from app.agents — patch the import path used
        import app.services.research_crew_service as crew_mod

        monkeypatch.setattr(crew_mod, "build_llm", lambda *_a, **_k: (_ for _ in ()).throw(StopAfterContext()))
        await service.run("INFY", rag=rag)

    assert captured.get("chroma_context")
    assert "Memory snippet" in (captured.get("chroma_context") or "")
