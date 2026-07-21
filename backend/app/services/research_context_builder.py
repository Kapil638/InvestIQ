"""Build immutable ResearchContext from collected pipeline data."""

from __future__ import annotations

from app.models.research_context import ResearchContext
from app.schemas.financial import FinancialResearchResponse
from app.schemas.news import NewsResearchResponse
from app.schemas.research import ResearchReportResponse
from app.services.data_snapshot import compute_data_snapshot_hash
from app.services.research_formatters import format_financial_summary, format_news_summary


def build_research_context(
    ticker: str,
    financial_data: FinancialResearchResponse | None,
    news_data: NewsResearchResponse | None,
    *,
    previous_report: ResearchReportResponse | None = None,
    chroma_context: str | None = None,
    portfolio_context: str | None = None,
) -> ResearchContext:
    symbol = ticker.strip().upper()
    data_hash = compute_data_snapshot_hash(symbol, financial_data, news_data)

    company_name = None
    latest_price = None
    valuation_metrics: dict[str, float | None] = {}

    if financial_data and financial_data.profile:
        company_name = financial_data.profile.company_name
        latest_price = financial_data.profile.price

    if financial_data and financial_data.ratios:
        ratio = financial_data.ratios[0]
        valuation_metrics = {
            "pe": ratio.price_to_earnings,
            "pb": ratio.price_to_book,
            "debt_to_equity": ratio.debt_to_equity,
            "roe": ratio.return_on_equity,
        }

    sentiment = None
    if news_data and news_data.sentiment_summary:
        sentiment = news_data.sentiment_summary

    previous_summary = _summarize_previous_report(previous_report)

    return ResearchContext(
        ticker=symbol,
        company_name=company_name,
        financial_data=financial_data,
        news_data=news_data,
        financial_summary=format_financial_summary(financial_data) if financial_data else "",
        news_summary=format_news_summary(news_data) if news_data else "",
        financial_summary_compact=(
            format_financial_summary(financial_data, compact=True) if financial_data else ""
        ),
        news_summary_compact=(
            format_news_summary(news_data, compact=True) if news_data else ""
        ),
        data_snapshot_hash=data_hash,
        latest_price=latest_price,
        valuation_metrics=valuation_metrics,
        market_sentiment=sentiment,
        previous_reports_summary=previous_summary,
        chroma_context=chroma_context,
        supabase_context=previous_summary,
        portfolio_context=portfolio_context,
        metadata={
            "financial_sources": financial_data.data_sources if financial_data else [],
            "news_article_count": len(news_data.latest_news) if news_data else 0,
        },
    )


def _summarize_previous_report(report: ResearchReportResponse | None) -> str | None:
    if not report:
        return None

    parts = [
        f"Prior report for {report.ticker}",
        f"Generated: {report.generated_at.isoformat()}",
    ]
    if report.confidence_score is not None:
        parts.append(f"Confidence: {report.confidence_score}")
    if report.recommendation:
        rec = report.recommendation
        parts.append(f"Rating: {rec.rating.value}")
        if rec.reasoning:
            parts.append(f"Prior reasoning:\n{rec.reasoning[:800]}")
        if rec.risks:
            parts.append("Prior key risks:\n" + "\n".join(f"- {r}" for r in rec.risks[:6]))
        if rec.target_price_range:
            parts.append(f"Prior target range: {rec.target_price_range}")
        if rec.investment_horizon:
            parts.append(f"Prior horizon: {rec.investment_horizon}")
    if report.analysis_output:
        scores = report.analysis_output.scores
        parts.append(
            "Prior analysis scores: "
            f"growth={scores.growth}, profitability={scores.profitability}, "
            f"valuation={scores.valuation}, health={scores.financial_health}, "
            f"overall={scores.overall}"
        )
    if report.risk_output:
        rs = report.risk_output.scores
        parts.append(
            "Prior risk scores: "
            f"overall_risk={rs.overall_risk}, "
            f"financial={rs.financial}, "
            f"business={rs.business}"
        )
    if report.analysis:
        parts.append(f"Prior investment thesis:\n{report.analysis[:1200]}")
    if report.confidence_change_reason:
        parts.append(f"Prior confidence change note: {report.confidence_change_reason}")
    if report.guardrails and not report.guardrails.passed:
        parts.append("Prior guardrails: FAILED — treat prior conclusions cautiously.")
    elif report.guardrails and report.guardrails.passed:
        parts.append("Prior guardrails: PASSED")

    return "\n".join(parts)

