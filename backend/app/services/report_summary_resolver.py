"""Resolve list/history rating and confidence from the full stored report."""

from __future__ import annotations

from app.schemas.research import ResearchReportResponse


def resolve_report_summary(
    report: ResearchReportResponse,
) -> tuple[str | None, float | None]:
    """
    Derive history-card rating/confidence using the same source as the detail view.

    Prefers investment committee verdict, then recommendation + committee mapping,
    then deterministic confidence bands.
    """
    confidence = _resolve_confidence(report)

    if report.investment_committee:
        verdict = report.investment_committee.verdict
        if confidence is None:
            confidence = float(verdict.overall_confidence)
        return verdict.final_recommendation.value, confidence

    from app.services.investment_committee_service import (
        InvestmentCommitteeService,
        _analyst_rating_from_confidence,
    )

    if report.recommendation or report.confidence_score is not None:
        enriched = InvestmentCommitteeService().enrich(report)
        if enriched.investment_committee:
            verdict = enriched.investment_committee.verdict
            if confidence is None:
                confidence = float(verdict.overall_confidence)
            return verdict.final_recommendation.value, confidence
        if report.recommendation:
            return report.recommendation.rating.value, confidence

    if report.confidence_score is not None:
        return (
            _analyst_rating_from_confidence(int(report.confidence_score)).value,
            float(report.confidence_score),
        )

    return None, None


def _resolve_confidence(report: ResearchReportResponse) -> float | None:
    if report.confidence_score is not None:
        return float(report.confidence_score)
    if report.recommendation and report.recommendation.confidence_score:
        return float(report.recommendation.confidence_score)
    return None
