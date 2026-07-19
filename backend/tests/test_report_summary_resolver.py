"""Tests for report history summary field resolution."""

from app.schemas.research import (
    GuardrailResult,
    RecommendationRating,
    ResearchReportResponse,
)
from app.services.investment_scoring_service import InvestmentScoringService
from app.services.report_summary_resolver import resolve_report_summary
from app.services.risk_extraction_service import extract_structured_risks
from tests.test_investment_scoring_service import _financial, _news


def _report_without_recommendation() -> ResearchReportResponse:
    fin = _financial().model_copy(update={"ticker": "INFY"})
    news = _news().model_copy(update={"ticker": "INFY"})
    analysis = (
        "Infosys revenue growth remains steady with downside risks from client spending. "
        "Key Risks:\n- Wage inflation\n- FX volatility"
    )
    structured = extract_structured_risks(analysis)
    draft = ResearchReportResponse(
        ticker="INFY",
        financial_data=fin,
        news_data=news,
        financial_data_summary="Solid fundamentals with margin pressure.",
        news_research_summary=news.sentiment_summary,
        analysis=analysis,
        structured_risks=structured,
        guardrails=GuardrailResult(passed=False, issues=[]),
        recommendation=None,
    )
    scoring = InvestmentScoringService().score(draft, structured_risks=structured)
    return draft.model_copy(
        update={
            "confidence_score": scoring.confidence_score,
            "score_breakdown": scoring.score_breakdown,
            "scoring_version": scoring.scoring_version,
        }
    )


def test_resolve_summary_uses_committee_verdict_without_recommendation() -> None:
    report = _report_without_recommendation()
    rating, confidence = resolve_report_summary(report)

    assert rating in {"BUY", "HOLD", "SELL", "AVOID"}
    assert confidence is not None
    assert confidence == report.confidence_score


def test_stored_from_report_populates_rating_when_recommendation_missing() -> None:
    from app.models.research_report import StoredResearchReport

    report = _report_without_recommendation()
    stored = StoredResearchReport.from_report("test-id", report)

    assert stored.rating is not None
    assert stored.confidence_score is not None
    assert stored.rating in {"BUY", "HOLD", "SELL", "AVOID"}


def test_resolve_summary_prefers_committee_over_raw_recommendation() -> None:
    report = _report_without_recommendation().model_copy(
        update={
            "recommendation": None,
            "confidence_score": 46,
        }
    )
    rating, confidence = resolve_report_summary(report)
    assert rating == "SELL"
    assert confidence == 46.0
