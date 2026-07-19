"""In-memory report repository for development and tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from app.models.research_report import StoredResearchReport
from app.schemas.research import ResearchReportResponse
from app.schemas.storage import ReportSummary
from app.services.report_summary_resolver import resolve_report_summary


class InMemoryReportRepository:
    """Thread-safe in-process storage – no external database required."""

    def __init__(self) -> None:
        self._reports: dict[str, StoredResearchReport] = {}
        self._lock = asyncio.Lock()

    async def save(self, report: ResearchReportResponse) -> StoredResearchReport:
        report_id = str(uuid4())
        stored = StoredResearchReport.from_report(report_id, report)
        async with self._lock:
            self._reports[report_id] = stored
        return stored

    async def get_by_id(self, report_id: str) -> StoredResearchReport | None:
        async with self._lock:
            return self._reports.get(report_id)

    async def list_reports(
        self,
        *,
        ticker: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ReportSummary], int]:
        async with self._lock:
            items = list(self._reports.values())

        if ticker:
            symbol = ticker.upper()
            items = [r for r in items if r.ticker == symbol]

        items.sort(key=lambda r: r.generated_at, reverse=True)
        total = len(items)
        page = items[offset : offset + limit]
        summaries = []
        for r in page:
            rating, confidence = resolve_report_summary(r.report)
            summaries.append(
                ReportSummary(
                    id=r.id,
                    ticker=r.ticker,
                    company_name=r.company_name,
                    rating=rating,
                    confidence_score=confidence,
                    guardrails_passed=r.guardrails_passed,
                    generated_at=r.generated_at,
                    pdf_generated_at=r.pdf_generated_at,
                    google_drive_file_id=r.google_drive_file_id,
                    google_drive_url=r.google_drive_url,
                    google_drive_saved_at=r.google_drive_saved_at,
                )
            )
        return summaries, total

    async def delete(self, report_id: str) -> bool:
        async with self._lock:
            return self._reports.pop(report_id, None) is not None

    async def find_latest_by_ticker(self, ticker: str) -> StoredResearchReport | None:
        async with self._lock:
            items = [r for r in self._reports.values() if r.ticker == ticker.upper()]
        if not items:
            return None
        items.sort(key=lambda r: r.generated_at, reverse=True)
        return items[0]

    async def update_export_metadata(
        self,
        report_id: str,
        *,
        pdf_generated_at: datetime | None = None,
        google_drive_file_id: str | None = None,
        google_drive_url: str | None = None,
        google_drive_saved_at: datetime | None = None,
    ) -> StoredResearchReport | None:
        async with self._lock:
            stored = self._reports.get(report_id)
            if stored is None:
                return None
            updated = stored.model_copy(
                update={
                    "pdf_generated_at": pdf_generated_at
                    if pdf_generated_at is not None
                    else stored.pdf_generated_at,
                    "google_drive_file_id": google_drive_file_id
                    if google_drive_file_id is not None
                    else stored.google_drive_file_id,
                    "google_drive_url": google_drive_url
                    if google_drive_url is not None
                    else stored.google_drive_url,
                    "google_drive_saved_at": google_drive_saved_at
                    if google_drive_saved_at is not None
                    else stored.google_drive_saved_at,
                }
            )
            self._reports[report_id] = updated
            return updated

    async def find_recent_by_ticker_and_hash(
        self,
        ticker: str,
        data_snapshot_hash: str,
        *,
        within_seconds: int = 120,
    ) -> StoredResearchReport | None:
        from datetime import UTC, datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(seconds=within_seconds)
        async with self._lock:
            items = [
                r
                for r in self._reports.values()
                if r.ticker == ticker.upper()
                and r.report.data_snapshot_hash == data_snapshot_hash
                and r.generated_at >= cutoff
            ]
        if not items:
            return None
        items.sort(key=lambda r: r.generated_at, reverse=True)
        return items[0]

    def clear(self) -> None:
        self._reports.clear()
