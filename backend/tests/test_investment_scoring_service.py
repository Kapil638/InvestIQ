"""Tests for deterministic investment committee scoring."""

from app.schemas.financial import (
    CompanyProfile,
    FinancialRatios,
    FinancialResearchResponse,
    IncomeStatement,
)
from app.schemas.news import NewsResearchResponse
from app.schemas.research import (
    GuardrailIssue,
    GuardrailResult,
    InvestmentRecommendation,
    RecommendationRating,
    ResearchReportResponse,
)
from app.services.data_snapshot import compute_data_snapshot_hash
from app.services.investment_scoring_service import InvestmentScoringService
from app.services.risk_extraction_service import extract_structured_risks


def _financial() -> FinancialResearchResponse:
    return FinancialResearchResponse(
        ticker="INFOBEAN",
        profile=CompanyProfile(symbol="INFOBEAN", company_name="InfoBeans"),
        income_statements=[
            IncomeStatement(date="2024-03-31", revenue=1000, net_income=120),
            IncomeStatement(date="2023-03-31", revenue=900, net_income=100),
        ],
        ratios=[
            FinancialRatios(
                date="2024-03-31",
                return_on_equity=0.16,
                net_profit_margin=0.12,
                debt_to_equity=0.4,
                price_to_earnings=22,
            )
        ],
        data_sources=["yahoo"],
    )


def _news() -> NewsResearchResponse:
    return NewsResearchResponse(
        ticker="INFOBEAN",
        sentiment_summary="Strong growth outlook with positive management commentary.",
    )


def _sample_report() -> ResearchReportResponse:
    fin = _financial()
    news = _news()
    analysis = (
        "Revenue growth remains healthy. Key Risks:\n"
        "- Client concentration risk\n"
        "- Margin pressure from wage inflation\n"
    )
    structured = extract_structured_risks(analysis)
    report = ResearchReportResponse(
        ticker="INFOBEAN",
        financial_data=fin,
        news_data=news,
        financial_data_summary="Strong fundamentals",
        news_research_summary=news.sentiment_summary,
        analysis=analysis,
        structured_risks=structured,
        guardrails=GuardrailResult(passed=True, issues=[]),
        recommendation=InvestmentRecommendation(
            rating=RecommendationRating.BUY,
            confidence_score=0,
            reasoning="Quality compounder.",
            risks=structured.risks,
            llm_suggested_confidence=82,
        ),
        data_snapshot_hash=compute_data_snapshot_hash("INFOBEAN", fin, news),
    )
    return report


def test_same_input_produces_same_confidence() -> None:
    report = _sample_report()
    service = InvestmentScoringService()
    first = service.score(report, structured_risks=report.structured_risks)
    second = service.score(report, structured_risks=report.structured_risks)
    assert first.confidence_score == second.confidence_score
    assert first.rating == second.rating
    assert first.score_breakdown == second.score_breakdown


def test_same_data_snapshot_hash_reuses_prior_scoring() -> None:
    report = _sample_report()
    service = InvestmentScoringService()
    first = service.score(report, structured_risks=report.structured_risks)
    prior = report.model_copy(
        update={
            "confidence_score": first.confidence_score,
            "score_breakdown": first.score_breakdown,
            "scoring_version": first.scoring_version,
            "data_snapshot_hash": first.data_snapshot_hash,
        }
    )
    second = service.score(prior, structured_risks=prior.structured_risks, previous_report=prior)
    assert second.reused_prior_scoring is True
    assert second.confidence_score == first.confidence_score


def test_missing_data_lowers_data_quality_score() -> None:
    report = _sample_report()
    report = report.model_copy(update={"news_data": None, "news_research_summary": None})
    service = InvestmentScoringService()
    with_news = service.score(_sample_report(), structured_risks=_sample_report().structured_risks)
    without_news = service.score(report, structured_risks=report.structured_risks)
    assert without_news.score_breakdown.data_quality_score < with_news.score_breakdown.data_quality_score


def test_guardrail_warnings_reduce_confidence() -> None:
    base = _sample_report()
    warned = base.model_copy(
        update={
            "guardrails": GuardrailResult(
                passed=True,
                issues=[GuardrailIssue(code="stale", message="Old news", severity="warning")],
            )
        }
    )
    service = InvestmentScoringService()
    base_score = service.score(base, structured_risks=base.structured_risks).confidence_score
    warned_score = service.score(warned, structured_risks=warned.structured_risks).confidence_score
    assert warned_score < base_score


def test_llm_confidence_not_used_as_source_of_truth() -> None:
    report = _sample_report()
    report = report.model_copy(
        update={
            "recommendation": report.recommendation.model_copy(
                update={"llm_suggested_confidence": 5}
            )
        }
    )
    scoring = InvestmentScoringService().score(report, structured_risks=report.structured_risks)
    assert scoring.confidence_score > 20
