"""Orchestrate report PDF generation and Google Drive export."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.research_report import StoredResearchReport
from app.schemas.research import ResearchReportResponse
from app.schemas.storage import ReportDriveSaveResponse
from app.services.google_drive_service import GoogleDriveService
from app.services.investment_committee_service import InvestmentCommitteeService
from app.services.report_pdf_service import build_report_pdf_filename, render_report_pdf
from app.services.report_storage_service import ReportStorageService
from app.utils.exceptions import ReportNotFoundError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ReportExportService:
    def __init__(
        self,
        storage: ReportStorageService,
        drive_service: GoogleDriveService,
    ) -> None:
        self._storage = storage
        self._drive = drive_service

    async def generate_pdf(self, report_id: str) -> tuple[bytes, str, ResearchReportResponse]:
        stored = await self._require_stored(report_id)
        report = InvestmentCommitteeService().enrich(stored.report)
        pdf_bytes = render_report_pdf(report)
        filename = build_report_pdf_filename(report)
        await self._storage.update_export_metadata(
            report_id,
            pdf_generated_at=datetime.now(UTC),
        )
        logger.info("Generated PDF for report %s (%s)", report_id, filename)
        return pdf_bytes, filename, report

    async def save_to_drive(self, report_id: str) -> ReportDriveSaveResponse:
        pdf_bytes, filename, _report = await self.generate_pdf(report_id)
        upload = await self._drive.upload_report_pdf(
            ticker=_report.ticker,
            filename=filename,
            pdf_bytes=pdf_bytes,
        )
        await self._storage.update_export_metadata(
            report_id,
            pdf_generated_at=datetime.now(UTC),
            google_drive_file_id=upload.file_id,
            google_drive_url=upload.url,
            google_drive_saved_at=datetime.now(UTC),
        )
        logger.info("Saved report %s PDF to Google Drive: %s", report_id, upload.url)
        return ReportDriveSaveResponse(
            success=True,
            drive_file_id=upload.file_id,
            drive_url=upload.url,
        )

    async def _require_stored(self, report_id: str) -> StoredResearchReport:
        stored = await self._storage.get(report_id)
        if not stored:
            raise ReportNotFoundError(f"Report not found: {report_id}")
        return stored
