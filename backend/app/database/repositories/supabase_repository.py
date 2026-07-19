"""Supabase PostgreSQL repository for research reports."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.models.research_report import StoredResearchReport
from app.schemas.research import ResearchReportResponse
from app.services.report_summary_resolver import resolve_report_summary
from app.schemas.storage import ReportSummary
from app.utils.exceptions import ExternalServiceError
from app.utils.logging import get_logger

logger = get_logger(__name__)

TABLE_NAME = "research_reports"


def _format_supabase_error(exc: Exception) -> str:
    """Extract a readable message from Supabase/postgrest API errors."""
    current: BaseException | None = exc
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))

        message = getattr(current, "message", None)
        if isinstance(message, dict) and message.get("message"):
            return str(message["message"])
        if isinstance(message, str) and message.strip():
            return message.strip()

        text = str(current).strip()
        has_nested = bool(current.__cause__ or current.__context__)
        if text and text != type(current).__name__ and not (current is exc and has_nested):
            return text

        current = current.__cause__ or current.__context__

    return str(exc)


class SupabaseReportRepository:
    """Persists reports to Supabase via the PostgREST API."""

    def __init__(self, url: str, key: str) -> None:
        self._url = url
        self._key = key
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from supabase import create_client
            except ImportError as exc:
                raise ImportError(
                    "supabase is required for PostgreSQL storage. "
                    "Install with: pip install supabase"
                ) from exc
            self._client = create_client(self._url, self._key)
        return self._client

    async def save(self, report: ResearchReportResponse) -> StoredResearchReport:
        report_id = str(uuid4())
        stored = StoredResearchReport.from_report(report_id, report)
        row = _to_row(stored)

        def _insert() -> None:
            response = self._get_client().table(TABLE_NAME).insert(row).execute()
            if getattr(response, "error", None):
                raise ExternalServiceError(str(response.error))

        try:
            await asyncio.to_thread(_insert)
        except ExternalServiceError:
            raise
        except Exception as exc:
            detail = _format_supabase_error(exc)
            logger.error("Supabase insert failed: %s", detail)
            raise ExternalServiceError(f"Failed to save research report: {detail}") from exc

        return stored

    async def get_by_id(self, report_id: str) -> StoredResearchReport | None:
        def _fetch() -> dict | None:
            response = (
                self._get_client()
                .table(TABLE_NAME)
                .select("*")
                .eq("id", report_id)
                .limit(1)
                .execute()
            )
            data = response.data or []
            return data[0] if data else None

        row = await asyncio.to_thread(_fetch)
        return _from_row(row) if row else None

    async def update_export_metadata(
        self,
        report_id: str,
        *,
        pdf_generated_at: datetime | None = None,
        google_drive_file_id: str | None = None,
        google_drive_url: str | None = None,
        google_drive_saved_at: datetime | None = None,
    ) -> StoredResearchReport | None:
        patch: dict[str, Any] = {}
        if pdf_generated_at is not None:
            patch["pdf_generated_at"] = pdf_generated_at.isoformat()
        if google_drive_file_id is not None:
            patch["google_drive_file_id"] = google_drive_file_id
        if google_drive_url is not None:
            patch["google_drive_url"] = google_drive_url
        if google_drive_saved_at is not None:
            patch["google_drive_saved_at"] = google_drive_saved_at.isoformat()
        if not patch:
            return await self.get_by_id(report_id)

        def _update() -> dict | None:
            response = (
                self._get_client()
                .table(TABLE_NAME)
                .update(patch)
                .eq("id", report_id)
                .execute()
            )
            data = response.data or []
            return data[0] if data else None

        row = await asyncio.to_thread(_update)
        return _from_row(row) if row else None

    async def list_reports(
        self,
        *,
        ticker: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ReportSummary], int]:
        def _fetch() -> tuple[list[dict], int]:
            query = self._get_client().table(TABLE_NAME).select("*", count="exact")
            if ticker:
                query = query.eq("ticker", ticker.upper())
            response = (
                query.order("generated_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
            rows = response.data or []
            total = response.count if response.count is not None else len(rows)
            return rows, total

        rows, total = await asyncio.to_thread(_fetch)
        summaries = [_to_summary(row) for row in rows]
        return summaries, total

    async def delete(self, report_id: str) -> bool:
        def _delete() -> bool:
            response = (
                self._get_client().table(TABLE_NAME).delete().eq("id", report_id).execute()
            )
            data = response.data or []
            return len(data) > 0

        return await asyncio.to_thread(_delete)

    async def find_latest_by_ticker(self, ticker: str) -> StoredResearchReport | None:
        def _fetch() -> dict | None:
            response = (
                self._get_client()
                .table(TABLE_NAME)
                .select("*")
                .eq("ticker", ticker.upper())
                .order("generated_at", desc=True)
                .limit(1)
                .execute()
            )
            data = response.data or []
            return data[0] if data else None

        row = await asyncio.to_thread(_fetch)
        return _from_row(row) if row else None

    async def find_recent_by_ticker_and_hash(
        self,
        ticker: str,
        data_snapshot_hash: str,
        *,
        within_seconds: int = 120,
    ) -> StoredResearchReport | None:
        from datetime import UTC, datetime, timedelta

        cutoff = (datetime.now(UTC) - timedelta(seconds=within_seconds)).isoformat()

        def _fetch() -> dict | None:
            response = (
                self._get_client()
                .table(TABLE_NAME)
                .select("*")
                .eq("ticker", ticker.upper())
                .order("generated_at", desc=True)
                .limit(20)
                .execute()
            )
            rows = response.data or []
            for row in rows:
                report_json = row.get("report_json") or {}
                if report_json.get("data_snapshot_hash") != data_snapshot_hash:
                    continue
                generated_at = row.get("generated_at") or report_json.get("generated_at")
                if generated_at and str(generated_at) >= cutoff:
                    return row
            return None

        row = await asyncio.to_thread(_fetch)
        return _from_row(row) if row else None


def _to_row(stored: StoredResearchReport) -> dict[str, Any]:
    row = {
        "id": stored.id,
        "ticker": stored.ticker,
        "company_name": stored.company_name,
        "rating": stored.rating,
        "confidence_score": stored.confidence_score,
        "guardrails_passed": stored.guardrails_passed,
        "generated_at": stored.generated_at.isoformat(),
        "report_json": stored.report.model_dump(mode="json"),
    }
    if stored.pdf_generated_at is not None:
        row["pdf_generated_at"] = stored.pdf_generated_at.isoformat()
    if stored.google_drive_file_id is not None:
        row["google_drive_file_id"] = stored.google_drive_file_id
    if stored.google_drive_url is not None:
        row["google_drive_url"] = stored.google_drive_url
    if stored.google_drive_saved_at is not None:
        row["google_drive_saved_at"] = stored.google_drive_saved_at.isoformat()
    return row


def _export_fields_from_row(row: dict[str, Any]) -> dict[str, Any]:
    pdf_generated_at = row.get("pdf_generated_at")
    google_drive_saved_at = row.get("google_drive_saved_at")
    return {
        "pdf_generated_at": _parse_optional_datetime(pdf_generated_at),
        "google_drive_file_id": row.get("google_drive_file_id"),
        "google_drive_url": row.get("google_drive_url"),
        "google_drive_saved_at": _parse_optional_datetime(google_drive_saved_at),
    }


def _parse_optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _from_row(row: dict[str, Any]) -> StoredResearchReport:
    report = ResearchReportResponse.model_validate(row["report_json"])
    export_fields = _export_fields_from_row(row)
    return StoredResearchReport(
        id=row["id"],
        ticker=row["ticker"],
        company_name=row.get("company_name"),
        rating=row.get("rating"),
        confidence_score=row.get("confidence_score"),
        guardrails_passed=row.get("guardrails_passed", False),
        generated_at=report.generated_at,
        report=report.model_copy(update={"id": row["id"]}),
        **export_fields,
    )


def _to_summary(row: dict[str, Any]) -> ReportSummary:
    report = ResearchReportResponse.model_validate(row["report_json"])
    rating, confidence = resolve_report_summary(report)
    export_fields = _export_fields_from_row(row)
    return ReportSummary(
        id=row["id"],
        ticker=row["ticker"],
        company_name=row.get("company_name"),
        rating=rating,
        confidence_score=confidence,
        guardrails_passed=row.get("guardrails_passed", False),
        generated_at=report.generated_at,
        **export_fields,
    )
