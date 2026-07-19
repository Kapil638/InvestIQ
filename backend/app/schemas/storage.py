"""API schemas for report storage and retrieval."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.research import ResearchReportResponse


class ReportSummary(BaseModel):
    id: str
    ticker: str
    company_name: str | None = None
    rating: str | None = None
    confidence_score: float | None = None
    guardrails_passed: bool
    generated_at: datetime
    pdf_generated_at: datetime | None = None
    google_drive_file_id: str | None = None
    google_drive_url: str | None = None
    google_drive_saved_at: datetime | None = None


class ReportListResponse(BaseModel):
    items: list[ReportSummary] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class SimilarReportMatch(BaseModel):
    report_id: str
    ticker: str
    snippet: str
    relevance_score: float
    rating: str | None = None
    generated_at: str | None = None


class SimilarReportsResponse(BaseModel):
    query: str
    ticker: str | None = None
    results: list[SimilarReportMatch] = Field(default_factory=list)


class StoredReportResponse(BaseModel):
    """Full stored report returned by detail endpoints."""

    id: str
    ticker: str
    company_name: str | None = None
    rating: str | None = None
    confidence_score: float | None = None
    guardrails_passed: bool
    generated_at: datetime
    report: ResearchReportResponse
    pdf_generated_at: datetime | None = None
    google_drive_file_id: str | None = None
    google_drive_url: str | None = None
    google_drive_saved_at: datetime | None = None


class BulkDeleteReportsRequest(BaseModel):
    report_ids: list[str] = Field(..., min_length=1, max_length=100)


class BulkDeleteReportsResponse(BaseModel):
    deleted: int
    not_found: list[str] = Field(default_factory=list)


class ReportDriveSaveResponse(BaseModel):
    success: bool = True
    drive_file_id: str
    drive_url: str
