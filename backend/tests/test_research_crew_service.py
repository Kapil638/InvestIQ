from contextlib import ExitStack
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.models.research_report import StoredResearchReport
from app.schemas.financial import (
    BalanceSheet,
    CompanyProfile,
    FinancialResearchResponse,
    IncomeStatement,
)
from app.schemas.news import NewsArticle, NewsResearchResponse
from app.schemas.research import GuardrailIssue, GuardrailResult, PipelineStageTrace, ResearchReportResponse
from app.guardrails.engine import GuardrailEngine
from app.services.research_crew_service import ResearchCrewService
from tests.pipeline_mocks import (
    ANALYSIS_CREW_OUTPUT,
    COLLECT_RETURN,
    RECOMMENDATION_CREW_OUTPUT,
    RISK_CREW_OUTPUT,
    SHORT_ANALYSIS_OUTPUT,
)


@pytest.fixture
def crew_settings() -> Settings:
    return Settings(
        yfinance_enabled=True,
        tavily_api_key="tavily-key",
        openrouter_api_key="openrouter-key",
        llm_provider="openrouter",
        crew_verbose=False,
    )


@pytest.fixture
def financial_data() -> FinancialResearchResponse:
    return FinancialResearchResponse(
        ticker="AAPL",
        collected_at=datetime.now(UTC),
        profile=CompanyProfile(symbol="AAPL", company_name="Apple Inc."),
        income_statements=[
            IncomeStatement(date="2026-03-28", revenue=1000000),
        ],
        balance_sheets=[
            BalanceSheet(date="2026-03-28", total_assets=500000, total_equity=300000),
        ],
    )


@pytest.fixture
def news_data() -> NewsResearchResponse:
    return NewsResearchResponse(
        ticker="AAPL",
        collected_at=datetime.now(UTC),
        latest_news=[
            NewsArticle(
                title="Apple news",
                url="https://example.com",
                published_date="2026-06-01",
            )
        ],
    )


def _enter_pipeline_mocks(service, financial_data, news_data, stack: ExitStack):
    stack.enter_context(
        patch.object(
            service,
            "_collect_structured_data_traced",
            new=AsyncMock(return_value=COLLECT_RETURN(financial_data, news_data)),
        )
    )
    stack.enter_context(
        patch.object(service, "_run_analysis_crew", new=AsyncMock(return_value=ANALYSIS_CREW_OUTPUT))
    )
    stack.enter_context(
        patch.object(service, "_run_risk_crew", new=AsyncMock(return_value=RISK_CREW_OUTPUT))
    )
    stack.enter_context(
        patch.object(
            service,
            "_run_recommendation_crew",
            new=AsyncMock(return_value=RECOMMENDATION_CREW_OUTPUT),
        )
    )
    mock_llm = stack.enter_context(patch("app.services.research_crew_service.build_llm"))
    mock_pairs = stack.enter_context(
        patch("app.tasks.research_tasks.build_reasoning_agent_pairs")
    )
    return mock_llm, mock_pairs


from datetime import UTC, datetime
async def test_run_executes_pipeline_stages(
    crew_settings: Settings,
    financial_data: FinancialResearchResponse,
    news_data: NewsResearchResponse,
) -> None:
    service = ResearchCrewService(settings=crew_settings)

    with ExitStack() as stack:
        mock_llm, mock_pairs = _enter_pipeline_mocks(service, financial_data, news_data, stack)
        mock_llm.return_value = MagicMock()
        mock_llm.return_value.model = "openrouter/openai/gpt-4o-mini"
        mock_pairs.return_value = {}
        report = await service.run("AAPL")

    assert report.ticker == "AAPL"
    assert report.financial_data is not None
    assert report.news_data is not None
    assert report.analysis is not None
    assert report.analysis_output is not None
    assert report.risk_output is not None
    assert report.guardrails is not None
    assert report.guardrails.passed is True
    assert report.risk_guardrails is not None
    assert report.recommendation_guardrails is not None
    assert report.recommendation is not None
    assert report.investment_committee is not None
    assert len(report.investment_committee.analysts) == 5
    trace_stages = {entry.stage for entry in report.pipeline_trace}
    assert "risk" in trace_stages
    assert "recommendation" in trace_stages
    assert "analysis" in trace_stages
    assert report.confidence_score is not None
    assert report.score_breakdown is not None
    assert report.scoring_version == "v2"
    assert report.structured_risks is not None
    assert report.structured_risks.source == "risk_agent"
    assert report.model_used == "openrouter/openai/gpt-4o-mini"


@pytest.mark.asyncio
async def test_run_retries_analysis_when_guardrails_are_retryable(
    crew_settings: Settings,
    financial_data: FinancialResearchResponse,
    news_data: NewsResearchResponse,
) -> None:
    service = ResearchCrewService(settings=crew_settings)
    crew_settings.guardrail_max_analysis_retries = 1

    with (
        patch.object(
            service,
            "_collect_structured_data_traced",
            new=AsyncMock(return_value=COLLECT_RETURN(financial_data, news_data)),
        ),
        patch.object(
            service,
            "_run_analysis_crew",
            new=AsyncMock(side_effect=[SHORT_ANALYSIS_OUTPUT, ANALYSIS_CREW_OUTPUT]),
        ),
        patch.object(service, "_run_risk_crew", new=AsyncMock(return_value=RISK_CREW_OUTPUT)),
        patch.object(
            service,
            "_run_recommendation_crew",
            new=AsyncMock(return_value=RECOMMENDATION_CREW_OUTPUT),
        ),
        patch("app.services.research_crew_service.build_llm") as mock_llm,
        patch("app.tasks.research_tasks.build_reasoning_agent_pairs") as mock_pairs,
    ):
        mock_llm.return_value = MagicMock()
        mock_pairs.return_value = {}
        report = await service.run("AAPL")

    assert report.guardrails is not None
    assert report.guardrails.retry_count == 1
    assert "strong revenue growth" in (report.analysis or "")
    assert report.recommendation is not None


@pytest.mark.asyncio
async def test_run_skips_recommendation_when_guardrails_fail(
    crew_settings: Settings,
    financial_data: FinancialResearchResponse,
    news_data: NewsResearchResponse,
) -> None:
    service = ResearchCrewService(settings=crew_settings)

    with (
        patch.object(
            service,
            "_collect_structured_data_traced",
            new=AsyncMock(return_value=COLLECT_RETURN(financial_data, news_data)),
        ),
        patch.object(service, "_run_analysis_crew", new=AsyncMock(return_value=SHORT_ANALYSIS_OUTPUT)),
        patch.object(service, "_run_risk_crew", new=AsyncMock(return_value=RISK_CREW_OUTPUT)),
        patch.object(service, "_run_recommendation_crew", new=AsyncMock()) as mock_recommendation,
        patch("app.services.research_crew_service.build_llm") as mock_llm,
        patch("app.tasks.research_tasks.build_reasoning_agent_pairs") as mock_pairs,
    ):
        mock_llm.return_value = MagicMock()
        mock_pairs.return_value = {}
        report = await service.run("AAPL")

    assert report.guardrails is not None
    assert report.guardrails.passed is False
    assert report.recommendation is None
    assert report.risk_output is not None
    assert report.risk_guardrails is not None
    assert report.recommendation_guardrails is None
    assert report.confidence_score is not None
    rec_stage = next(e for e in report.pipeline_trace if e.stage == "recommendation")
    assert rec_stage.status == "skipped"
    mock_recommendation.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_builds_evidence_corpus_once(
    crew_settings: Settings,
    financial_data: FinancialResearchResponse,
    news_data: NewsResearchResponse,
) -> None:
    service = ResearchCrewService(settings=crew_settings)

    with ExitStack() as stack:
        _enter_pipeline_mocks(service, financial_data, news_data, stack)
        corpus_mock = stack.enter_context(
            patch(
                "app.services.research_crew_service.build_evidence_corpus",
                wraps=__import__(
                    "app.guardrails.evidence", fromlist=["build_evidence_corpus"]
                ).build_evidence_corpus,
            )
        )
        await service.run("AAPL")

    assert corpus_mock.call_count == 1


@pytest.mark.asyncio
async def test_risk_guardrail_failure_does_not_block_report(
    crew_settings: Settings,
    financial_data: FinancialResearchResponse,
    news_data: NewsResearchResponse,
) -> None:
    service = ResearchCrewService(settings=crew_settings)
    real_validate = GuardrailEngine.validate

    def validate_with_risk_failure(self, ticker, financial_data, news_data, text, *, corpus=None):
        result = real_validate(self, ticker, financial_data, news_data, text, corpus=corpus)
        if text and "regulatory headwinds" in text:
            return GuardrailResult(
                passed=False,
                issues=[
                    GuardrailIssue(
                        code="unsupported_numeric_claims",
                        message="Unsupported claim in risk narrative",
                        severity="error",
                    )
                ],
                blocked_reason="unsupported_numeric_claims: Unsupported claim in risk narrative",
            )
        return result

    with ExitStack() as stack:
        _enter_pipeline_mocks(service, financial_data, news_data, stack)
        stack.enter_context(
            patch.object(GuardrailEngine, "validate", validate_with_risk_failure)
        )
        report = await service.run("AAPL")

    assert report.risk_guardrails is not None
    assert report.risk_guardrails.passed is False
    assert report.recommendation is not None
    risk_stage = next(e for e in report.pipeline_trace if e.stage == "risk")
    assert risk_stage.detail is not None
    assert "guardrails_failed" in risk_stage.detail


@pytest.mark.asyncio
async def test_run_returns_cached_report_when_same_hash_within_2_minutes(
    crew_settings: Settings,
    financial_data: FinancialResearchResponse,
    news_data: NewsResearchResponse,
) -> None:
    service = ResearchCrewService(settings=crew_settings)
    cached_body = ResearchReportResponse(
        ticker="AAPL",
        financial_data=financial_data,
        news_data=news_data,
        financial_data_summary="cached summary",
        news_research_summary="cached news",
        analysis="Cached analysis with enough length for validation purposes.",
        guardrails=GuardrailResult(passed=True, issues=[]),
        confidence_score=68,
        scoring_version="v1",
        pipeline_trace=[
            PipelineStageTrace(
                stage="committee",
                status="completed",
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_ms=1,
            )
        ],
    )
    cached = StoredResearchReport(
        id="cached-report-id",
        ticker="AAPL",
        generated_at=datetime.now(UTC),
        report=cached_body,
    )
    mock_storage = AsyncMock()
    mock_storage.find_latest_by_ticker = AsyncMock(return_value=None)
    mock_storage.find_recent_by_ticker_and_hash = AsyncMock(return_value=cached)

    with (
        patch.object(
            service,
            "_collect_structured_data_traced",
            new=AsyncMock(return_value=COLLECT_RETURN(financial_data, news_data)),
        ),
        patch.object(service, "_run_analysis_crew", new=AsyncMock()) as mock_analysis,
        patch.object(service, "_run_risk_crew", new=AsyncMock()) as mock_risk,
        patch.object(service, "_run_recommendation_crew", new=AsyncMock()) as mock_recommendation,
    ):
        report = await service.run("AAPL", storage=mock_storage)

    assert report.regenerated_from_same_data is True
    assert report.confidence_score == 68
    mock_analysis.assert_not_awaited()
    mock_risk.assert_not_awaited()
    mock_recommendation.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_handles_previous_stored_report_for_scoring(
    crew_settings: Settings,
    financial_data: FinancialResearchResponse,
    news_data: NewsResearchResponse,
) -> None:
    from app.services.data_snapshot import compute_data_snapshot_hash

    service = ResearchCrewService(settings=crew_settings)
    data_hash = compute_data_snapshot_hash("AAPL", financial_data, news_data)
    prior_report = ResearchReportResponse(
        ticker="AAPL",
        financial_data=financial_data,
        news_data=news_data,
        financial_data_summary="prior",
        news_research_summary="prior news",
        analysis=ANALYSIS_CREW_OUTPUT,
        guardrails=GuardrailResult(passed=True, issues=[]),
        confidence_score=65,
        scoring_version="v1",
        data_snapshot_hash=data_hash,
        pipeline_trace=[],
    )
    prior_stored = StoredResearchReport(
        id="prior-id",
        ticker="AAPL",
        generated_at=datetime.now(UTC),
        report=prior_report,
    )
    mock_storage = AsyncMock()
    mock_storage.find_latest_by_ticker = AsyncMock(return_value=prior_stored)
    mock_storage.find_recent_by_ticker_and_hash = AsyncMock(return_value=None)

    with ExitStack() as stack:
        mock_llm, mock_pairs = _enter_pipeline_mocks(service, financial_data, news_data, stack)
        mock_llm.return_value = MagicMock()
        mock_pairs.return_value = {}
        report = await service.run("AAPL", storage=mock_storage)

    assert report.confidence_score is not None
    mock_storage.find_latest_by_ticker.assert_awaited_once_with("AAPL")
