from app.schemas.financial import CompanyProfile, FinancialResearchResponse
from app.schemas.news import NewsArticle, NewsResearchResponse
from app.schemas.research import (
    GuardrailResult,
    InvestmentRecommendation,
    RecommendationRating,
    ResearchReportResponse,
)
from app.services.investment_committee_service import InvestmentCommitteeService
from app.services.investment_scoring_service import InvestmentScoringService
from app.services.research_formatters import format_financial_summary, format_news_summary
from app.services.risk_extraction_service import extract_structured_risks


def _sample_report() -> ResearchReportResponse:
    analysis = (
        "Infosys shows improving momentum with bullish trend signals. "
        "Valuation at reasonable P/E multiples versus peers. "
        "Key downside risks include wage inflation and client spending cycles."
    )
    return ResearchReportResponse(
        ticker="INFY.NS",
        financial_data_summary=(
            "Strong revenue growth with healthy ROE. Debt levels remain manageable. "
            "Cash flow generation supports dividends."
        ),
        news_research_summary=(
            "Management commentary remains constructive. Recent announcements highlight "
            "large deal wins and steady client demand."
        ),
        analysis=analysis,
        structured_risks=extract_structured_risks(analysis),
        guardrails=GuardrailResult(passed=True, issues=[]),
        recommendation=InvestmentRecommendation(
            rating=RecommendationRating.BUY,
            confidence_score=0,
            reasoning="Quality compounder with resilient margins and improving deal pipeline.",
            risks=["Wage inflation", "FX volatility", "Client spending slowdown"],
            investment_horizon="3-year core holding",
            target_price_range="INR 1,650 – 1,750",
            llm_suggested_confidence=78,
        ),
    )


def test_investment_committee_builds_five_analysts() -> None:
    committee = InvestmentCommitteeService().build(_sample_report())
    assert len(committee.analysts) == 5
    ids = {a.id.value for a in committee.analysts}
    assert ids == {"fundamental", "news", "technical", "valuation", "risk"}


def test_investment_committee_verdict_matches_buy() -> None:
    report = _sample_report()
    scoring = InvestmentScoringService().score(report, structured_risks=report.structured_risks)
    report = report.model_copy(
        update={
            "confidence_score": scoring.confidence_score,
            "score_breakdown": scoring.score_breakdown,
            "recommendation": report.recommendation.model_copy(
                update={
                    "rating": scoring.rating,
                    "confidence_score": float(scoring.confidence_score),
                }
            ),
        }
    )
    committee = InvestmentCommitteeService().build(report)
    assert committee.verdict.final_recommendation.value in {"BUY", "HOLD", "SELL", "AVOID"}
    assert committee.verdict.overall_confidence == scoring.confidence_score
    assert committee.verdict.bull_case
    assert committee.verdict.bear_case


def test_investment_committee_enriches_report() -> None:
    report = _sample_report()
    assert report.investment_committee is None
    enriched = InvestmentCommitteeService().enrich(report)
    assert enriched.investment_committee is not None
    assert enriched.investment_committee.verdict.final_recommendation.value == "BUY"


def test_risk_analyst_more_conservative_than_base() -> None:
    committee = InvestmentCommitteeService().build(_sample_report())
    risk = next(a for a in committee.analysts if a.id.value == "risk")
    assert risk.recommendation.value in {"HOLD", "SELL", "AVOID"}


def test_avoid_maps_to_sell_when_high_confidence() -> None:
    report = _sample_report()
    report.recommendation.rating = RecommendationRating.AVOID
    report.recommendation.confidence_score = 80
    committee = InvestmentCommitteeService().build(report)
    assert committee.verdict.final_recommendation.value == "SELL"


def _looks_like_raw_json_line(text: str) -> bool:
    """Heuristic matching the actual leaked lines observed in production,
    e.g. `"ticker": "RELIABLE.NS",` or `"company_name": null,`."""
    stripped = text.strip()
    return stripped.startswith('"') and '":' in stripped


def test_fundamental_analyst_does_not_leak_json_summary_into_points() -> None:
    """Regression test: financial_data_summary is a JSON blob built for LLM
    prompt context (research_formatters.format_financial_summary), not for
    display. Previously it was split directly into UI bullet points, leaking
    raw lines like `"ticker": "X",` into the Fundamental Analyst card."""
    financial_data = FinancialResearchResponse(
        ticker="RELIABLE.NS",
        profile=CompanyProfile(
            symbol="RELIABLE",
            company_name="Reliable Data Services Limited",
            sector="Technology",
            industry="Information Technology Services",
            market_cap=1_513_943_936.0,
        ),
    )
    report = _sample_report().model_copy(
        update={
            "financial_data": financial_data,
            "financial_data_summary": format_financial_summary(financial_data),
        }
    )

    committee = InvestmentCommitteeService().build(report)
    fundamental = next(a for a in committee.analysts if a.id.value == "fundamental")

    assert fundamental.supporting_points, "must still produce some points"
    assert not any(_looks_like_raw_json_line(p) for p in fundamental.supporting_points)


def test_news_analyst_does_not_leak_json_summary_and_uses_real_headlines() -> None:
    """Regression test: news_research_summary is also a JSON blob (see
    research_formatters.format_news_summary). The previous fallback for real
    headlines referenced report.news_data.articles, which doesn't exist on
    NewsResearchResponse (the real fields are latest_news/sector_news/
    earnings_and_filings) and would have raised AttributeError if reached."""
    news_data = NewsResearchResponse(
        ticker="RELIABLE",
        latest_news=[
            NewsArticle(title="Reliable Data Services wins new enterprise contract", url="https://example.com/1"),
            NewsArticle(title="Quarterly results beat street estimates", url="https://example.com/2"),
        ],
    )
    report = _sample_report().model_copy(
        update={
            "news_data": news_data,
            "news_research_summary": format_news_summary(news_data),
        }
    )

    committee = InvestmentCommitteeService().build(report)
    news = next(a for a in committee.analysts if a.id.value == "news")

    assert news.supporting_points, "must still produce some points"
    assert not any(_looks_like_raw_json_line(p) for p in news.supporting_points)
    assert "Reliable Data Services wins new enterprise contract" in news.supporting_points
