"""Report storage and RAG retrieval endpoints."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.api.dependencies import (
    get_rag_service,
    get_report_chat_service,
    get_report_export_service,
    get_report_storage_service,
)
from app.schemas.chat import ReportChatRequest, ReportChatResponse
from app.schemas.storage import (
    BulkDeleteReportsRequest,
    BulkDeleteReportsResponse,
    ReportDriveSaveResponse,
    ReportListResponse,
    SimilarReportsResponse,
    StoredReportResponse,
)
from app.services.rag_service import RagService
from app.services.investment_committee_service import InvestmentCommitteeService
from app.services.report_chat_service import ReportChatService
from app.services.report_export_service import ReportExportService
from app.services.report_storage_service import ReportStorageService
from app.services.report_summary_resolver import resolve_report_summary
from app.utils.exceptions import ReportNotFoundError
from app.utils import ttl_cache

router = APIRouter(tags=["reports"])


@router.get("/reports", response_model=ReportListResponse)
async def list_reports(
    ticker: str | None = Query(default=None, description="Filter by ticker symbol"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    storage: ReportStorageService = Depends(get_report_storage_service),
) -> ReportListResponse:
    """List stored research reports, newest first."""
    items, total = await storage.list_reports(ticker=ticker, limit=limit, offset=offset)
    return ReportListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/reports/bulk-delete", response_model=BulkDeleteReportsResponse)
async def bulk_delete_reports(
    body: BulkDeleteReportsRequest,
    storage: ReportStorageService = Depends(get_report_storage_service),
) -> BulkDeleteReportsResponse:
    """Delete multiple stored research reports."""
    deleted, not_found = await storage.bulk_delete(body.report_ids)
    return BulkDeleteReportsResponse(deleted=deleted, not_found=not_found)


@router.get("/reports/search/similar", response_model=SimilarReportsResponse)
async def search_similar_reports(
    query: str = Query(..., min_length=3, description="Semantic search query"),
    ticker: str | None = Query(default=None, description="Optional ticker filter"),
    limit: int = Query(default=5, ge=1, le=20),
    rag: RagService = Depends(get_rag_service),
) -> SimilarReportsResponse:
    """
    RAG search – find similar past research reports using ChromaDB.

    Useful for comparing current analysis against institutional memory.
    """
    return await rag.search_similar(query, ticker=ticker, limit=limit)


@router.get("/reports/ticker/{ticker}", response_model=ReportListResponse)
async def list_reports_by_ticker(
    ticker: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    storage: ReportStorageService = Depends(get_report_storage_service),
) -> ReportListResponse:
    """List all stored reports for a specific ticker."""
    items, total = await storage.list_reports(ticker=ticker, limit=limit, offset=offset)
    return ReportListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/reports/{report_id}/chat", response_model=ReportChatResponse)
async def chat_about_report(
    report_id: str,
    body: ReportChatRequest,
    chat_service: ReportChatService = Depends(get_report_chat_service),
) -> ReportChatResponse:
    """
    Ask a follow-up question about a saved research report.

    Uses stored report content + optional ChromaDB memory. Does not re-run CrewAI.
    """
    return await chat_service.chat(report_id, body.question, body.history)


@router.get("/reports/{report_id}", response_model=StoredReportResponse)
async def get_report(
    report_id: str,
    storage: ReportStorageService = Depends(get_report_storage_service),
) -> StoredReportResponse:
    """Retrieve a single stored research report by ID."""
    cached = ttl_cache.get("report", report_id)
    if cached is not None:
        return cached

    stored = await storage.get(report_id)
    if not stored:
        raise ReportNotFoundError(f"Report not found: {report_id}")

    report = InvestmentCommitteeService().enrich(stored.report)
    rating, confidence = resolve_report_summary(report)

    response = StoredReportResponse(
        id=stored.id,
        ticker=stored.ticker,
        company_name=stored.company_name,
        rating=rating,
        confidence_score=confidence,
        guardrails_passed=stored.guardrails_passed,
        generated_at=stored.generated_at,
        report=report,
        pdf_generated_at=stored.pdf_generated_at,
        google_drive_file_id=stored.google_drive_file_id,
        google_drive_url=stored.google_drive_url,
        google_drive_saved_at=stored.google_drive_saved_at,
    )
    ttl_cache.set("report", report_id, response)
    return response


@router.delete("/reports/{report_id}", status_code=204)
async def delete_report(
    report_id: str,
    storage: ReportStorageService = Depends(get_report_storage_service),
) -> None:
    """Delete a stored research report."""
    deleted = await storage.delete(report_id)
    if not deleted:
        raise ReportNotFoundError(f"Report not found: {report_id}")


@router.post("/reports/{report_id}/pdf")
async def generate_report_pdf(
    report_id: str,
    export_service: ReportExportService = Depends(get_report_export_service),
) -> Response:
    """Generate and download a professional PDF for a stored report."""
    pdf_bytes, filename, _report = await export_service.generate_pdf(report_id)
    disposition = f'attachment; filename="{quote(filename)}"'
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )


@router.post("/reports/{report_id}/drive")
async def save_report_to_google_drive(
    report_id: str,
    export_service: ReportExportService = Depends(get_report_export_service),
) -> ReportDriveSaveResponse:
    """Upload the report PDF to Google Drive and persist Drive metadata."""
    return await export_service.save_to_drive(report_id)
