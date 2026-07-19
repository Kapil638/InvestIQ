"""Build LLM context strings from stored research reports."""

from __future__ import annotations

from app.models.research_report import StoredResearchReport
from app.schemas.storage import ReportSummary

_UNAVAILABLE = "Not available in this report."


def build_report_context(stored: StoredResearchReport) -> str:
    """Serialize a stored report into a single context block for LLM chat."""
    report = stored.report
    parts = [
        f"Report ID: {stored.id}",
        f"Ticker: {stored.ticker}",
        f"Company: {stored.company_name or 'Unknown'}",
        f"Generated: {stored.generated_at.isoformat()}",
        f"Rating: {stored.rating or 'No rating'}",
        f"Confidence: {stored.confidence_score if stored.confidence_score is not None else 'N/A'}",
        f"Guardrails passed: {stored.guardrails_passed}",
    ]

    if report.financial_data and report.financial_data.profile:
        profile = report.financial_data.profile
        if profile.description:
            parts.append(f"Company description:\n{profile.description}")
        if profile.sector:
            parts.append(f"Sector: {profile.sector}")
        if profile.industry:
            parts.append(f"Industry: {profile.industry}")

    if report.financial_data_summary:
        parts.append(f"Financial summary:\n{report.financial_data_summary}")

    if report.news_research_summary:
        parts.append(f"News summary:\n{report.news_research_summary}")

    if report.analysis:
        parts.append(f"Investment thesis / analysis:\n{report.analysis}")

    if report.guardrails and report.guardrails.issues:
        issues = "\n".join(f"- [{i.severity}] {i.message}" for i in report.guardrails.issues)
        parts.append(f"Guardrail notes:\n{issues}")

    if report.recommendation:
        rec = report.recommendation
        risks = "\n".join(f"- {r}" for r in rec.risks) if rec.risks else _UNAVAILABLE
        parts.append(
            "Recommendation:\n"
            f"Rating: {rec.rating.value}\n"
            f"Confidence: {rec.confidence_score}\n"
            f"Reasoning: {rec.reasoning}\n"
            f"Risks:\n{risks}\n"
            f"Target price range: {rec.target_price_range or _UNAVAILABLE}\n"
            f"Investment horizon: {rec.investment_horizon or _UNAVAILABLE}\n"
            f"Allocation suggestion: {rec.portfolio_allocation_suggestion or _UNAVAILABLE}"
        )

    return "\n\n".join(parts)


def build_previous_reports_context(
    summaries: list[ReportSummary],
    *,
    exclude_id: str,
    limit: int = 3,
) -> str:
    """Summarize prior reports for the same ticker (for change-over-time questions)."""
    prior = [s for s in summaries if s.id != exclude_id][:limit]
    if not prior:
        return ""

    lines = ["Previous reports for this ticker:"]
    for item in prior:
        lines.append(
            f"- [{item.generated_at.isoformat()}] id={item.id} "
            f"rating={item.rating or 'N/A'} confidence={item.confidence_score or 'N/A'} "
            f"guardrails_passed={item.guardrails_passed}"
        )
    return "\n".join(lines)


def build_index_chunks(stored: StoredResearchReport) -> list[tuple[str, str]]:
    """Section chunks for ChromaDB semantic search."""
    report = stored.report
    chunks: list[tuple[str, str]] = []

    header = (
        f"Ticker: {stored.ticker} | Company: {stored.company_name or 'Unknown'} | "
        f"Rating: {stored.rating or 'N/A'} | Generated: {stored.generated_at.isoformat()}"
    )
    chunks.append(("header", header))

    if report.financial_data_summary:
        chunks.append(("financial", report.financial_data_summary))
    if report.news_research_summary:
        chunks.append(("news", report.news_research_summary))
    if report.analysis:
        chunks.append(("analysis", report.analysis))
    if report.recommendation:
        rec = report.recommendation
        chunks.append(
            (
                "recommendation",
                f"{rec.rating.value} ({rec.confidence_score}%): {rec.reasoning}",
            )
        )
        if rec.risks:
            chunks.append(("risks", "\n".join(rec.risks)))

    return chunks
