"""Architecture regression tests for refactored research pipeline."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.guardrails.structured_output_parser import parse_analysis_output, parse_risk_output
from app.models.research_context import ResearchContext
from app.schemas.financial import CompanyProfile, FinancialResearchResponse
from app.schemas.news import NewsResearchResponse
from app.schemas.research import GuardrailResult, ResearchReportResponse
from app.services.data_snapshot import compute_data_snapshot_hash
from app.services.investment_scoring_service import InvestmentScoringService
from app.services.research_context_builder import build_research_context
from app.services.research_crew_service import ResearchCrewService
from app.services.stage_cache import get_stage, set_stage
from tests.pipeline_mocks import ANALYSIS_CREW_OUTPUT, RISK_CREW_OUTPUT


@pytest.fixture
def settings() -> Settings:
    return Settings(
        yfinance_enabled=True,
        tavily_api_key="tavily-key",
        openrouter_api_key="openrouter-key",
        llm_provider="openrouter",
        crew_verbose=False,
        cache_enabled=True,
    )


def test_research_context_is_immutable_and_shared_fields() -> None:
    fin = FinancialResearchResponse(
        ticker="INFY",
        profile=CompanyProfile(symbol="INFY", company_name="Infosys", price=1500.0),
    )
    news = NewsResearchResponse(ticker="INFY", sentiment_summary="Positive outlook")
    ctx = build_research_context("INFY", fin, news)
    assert isinstance(ctx, ResearchContext)
    assert ctx.ticker == "INFY"
    assert ctx.data_snapshot_hash == compute_data_snapshot_hash("INFY", fin, news)
    assert "INFY" in ctx.to_agent_prompt_block()
    with pytest.raises(Exception):
        ctx.ticker = "TCS"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_financial_and_news_collect_run_in_parallel(settings: Settings) -> None:
    service = ResearchCrewService(settings=settings)
    order: list[str] = []

    async def slow_fin(_symbol):
        order.append("fin_start")
        await asyncio.sleep(0.05)
        order.append("fin_end")
        return FinancialResearchResponse(
            ticker="INFY",
            profile=CompanyProfile(symbol="INFY", company_name="Infosys"),
        )

    async def slow_news(_symbol):
        order.append("news_start")
        await asyncio.sleep(0.05)
        order.append("news_end")
        return NewsResearchResponse(ticker="INFY")

    from app.services.pipeline_tracer import PipelineTracer

    tracer = PipelineTracer()
    with (
        patch("app.services.research_crew_service.build_financial_data_service") as mock_fin_svc,
        patch("app.services.research_crew_service.NewsResearchService") as mock_news_cls,
        patch("app.services.research_crew_service.TavilyClient") as mock_tavily,
        patch("app.services.research_crew_service.get_stage", return_value=None),
    ):
        mock_fin_svc.return_value.collect = slow_fin
        mock_news_cls.return_value.collect = slow_news
        mock_tavily.return_value.close = AsyncMock()
        await service._collect_structured_data_traced("INFY", tracer, [])

    assert "fin_start" in order and "news_start" in order
    assert max(order.index("fin_start"), order.index("news_start")) < min(
        order.index("fin_end"), order.index("news_end")
    )


def test_committee_score_deterministic_from_agent_outputs() -> None:
    analysis = parse_analysis_output(ANALYSIS_CREW_OUTPUT)
    risk = parse_risk_output(RISK_CREW_OUTPUT)
    report = ResearchReportResponse(
        ticker="INFY",
        analysis=analysis.narrative,
        analysis_output=analysis,
        risk_output=risk,
        guardrails=GuardrailResult(passed=True, issues=[]),
        data_snapshot_hash="abc123",
    )
    svc = InvestmentScoringService()
    first = svc.score(report)
    second = svc.score(report)
    assert first.confidence_score == second.confidence_score
    assert first.scoring_version == "v2"


def test_stage_cache_reuses_analysis() -> None:
    from app.utils import ttl_cache

    ttl_cache.clear_all()
    fin = FinancialResearchResponse(
        ticker="INFY",
        profile=CompanyProfile(symbol="INFY", company_name="Infosys"),
    )
    news = NewsResearchResponse(ticker="INFY")
    data_hash = compute_data_snapshot_hash("INFY", fin, news)
    payload = parse_analysis_output(ANALYSIS_CREW_OUTPUT).model_dump()

    with patch("app.utils.ttl_cache._enabled", return_value=True):
        set_stage("analysis", data_hash, payload)
        assert get_stage("analysis", data_hash) is not None
