"""Domain models for persisted research reports."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.research import ResearchReportResponse
from app.services.report_summary_resolver import resolve_report_summary


class StoredResearchReport(BaseModel):
    """A research report persisted in Supabase with a stable ID."""

    id: str
    ticker: str
    company_name: str | None = None
    rating: str | None = None
    confidence_score: float | None = None
    guardrails_passed: bool = False
    generated_at: datetime
    report: ResearchReportResponse
    pdf_generated_at: datetime | None = None
    google_drive_file_id: str | None = None
    google_drive_url: str | None = None
    google_drive_saved_at: datetime | None = None

    @classmethod
    def from_report(cls, report_id: str, report: ResearchReportResponse) -> "StoredResearchReport":
        company_name = None
        if report.financial_data and report.financial_data.profile:
            company_name = report.financial_data.profile.company_name

        rating, confidence = resolve_report_summary(report)

        guardrails_passed = bool(report.guardrails and report.guardrails.passed)

        return cls(
            id=report_id,
            ticker=report.ticker,
            company_name=company_name,
            rating=rating,
            confidence_score=confidence,
            guardrails_passed=guardrails_passed,
            generated_at=report.generated_at,
            report=report.model_copy(update={"id": report_id}),
        )
