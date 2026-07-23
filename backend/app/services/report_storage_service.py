"""Persist research reports and index them for RAG."""

from app.database.pgvector_store import PgVectorStore
from app.database.repositories.memory_repository import InMemoryReportRepository
from app.models.research_report import StoredResearchReport
from app.schemas.research import ResearchReportResponse
from app.services.report_context import build_index_chunks
from app.utils import ttl_cache
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ReportStorageService:
    """Saves reports to Supabase (or memory) and indexes them for RAG (pgvector)."""

    def __init__(self, repository, vector_store: PgVectorStore | None) -> None:
        self._repository = repository
        self._vector_store = vector_store

    @property
    def is_persistence_enabled(self) -> bool:
        return self._repository is not None

    async def save(self, report: ResearchReportResponse) -> StoredResearchReport:
        stored = await self._repository.save(report)

        if self._vector_store:
            document = _build_index_document(stored)
            chunks = build_index_chunks(stored)
            try:
                await self._vector_store.index_report(
                    report_id=stored.id,
                    ticker=stored.ticker,
                    document=document,
                    rating=stored.rating,
                    generated_at=stored.generated_at.isoformat(),
                )
                await self._vector_store.index_report_chunks(
                    report_id=stored.id,
                    ticker=stored.ticker,
                    chunks=chunks,
                    rating=stored.rating,
                    generated_at=stored.generated_at.isoformat(),
                )
            except Exception as exc:
                logger.warning("pgvector indexing failed for %s: %s", stored.id, exc)

        return stored

    async def get(self, report_id: str) -> StoredResearchReport | None:
        return await self._repository.get_by_id(report_id)

    async def list_reports(
        self,
        *,
        ticker: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ):
        return await self._repository.list_reports(
            ticker=ticker, limit=limit, offset=offset
        )

    async def delete(self, report_id: str) -> bool:
        deleted = await self._repository.delete(report_id)
        if not deleted:
            return False

        ttl_cache.delete("report", report_id)
        ttl_cache.delete("chat_context", report_id)

        if self._vector_store:
            try:
                await self._vector_store.delete_report(report_id)
            except Exception as exc:
                logger.warning("pgvector delete failed for %s: %s", report_id, exc)

        return True

    async def find_latest_by_ticker(self, ticker: str):
        finder = getattr(self._repository, "find_latest_by_ticker", None)
        if finder is None:
            return None
        return await finder(ticker)

    async def find_recent_by_ticker_and_hash(
        self, ticker: str, data_snapshot_hash: str, *, within_seconds: int = 120
    ):
        finder = getattr(self._repository, "find_recent_by_ticker_and_hash", None)
        if finder is None:
            return None
        return await finder(ticker, data_snapshot_hash, within_seconds=within_seconds)

    async def bulk_delete(self, report_ids: list[str]) -> tuple[int, list[str]]:
        deleted = 0
        not_found: list[str] = []
        for report_id in report_ids:
            if await self.delete(report_id):
                deleted += 1
            else:
                not_found.append(report_id)
        return deleted, not_found

    async def update_export_metadata(
        self,
        report_id: str,
        *,
        pdf_generated_at=None,
        google_drive_file_id: str | None = None,
        google_drive_url: str | None = None,
        google_drive_saved_at=None,
    ) -> StoredResearchReport | None:
        updater = getattr(self._repository, "update_export_metadata", None)
        if updater is None:
            return await self.get(report_id)

        updated = await updater(
            report_id,
            pdf_generated_at=pdf_generated_at,
            google_drive_file_id=google_drive_file_id,
            google_drive_url=google_drive_url,
            google_drive_saved_at=google_drive_saved_at,
        )
        if updated:
            ttl_cache.delete("report", report_id)
        return updated


def _build_index_document(stored: StoredResearchReport) -> str:
    """Combine key report text for semantic search."""
    parts = [
        f"Ticker: {stored.ticker}",
        f"Company: {stored.company_name or 'Unknown'}",
    ]
    report = stored.report
    if report.financial_data_summary:
        parts.append(f"Financial Summary:\n{report.financial_data_summary}")
    if report.news_research_summary:
        parts.append(f"News Summary:\n{report.news_research_summary}")
    if report.analysis:
        parts.append(f"Analysis:\n{report.analysis}")
    if report.recommendation:
        rec = report.recommendation
        parts.append(
            f"Recommendation: {rec.rating.value} "
            f"(confidence {rec.confidence_score})\n{rec.reasoning}"
        )
    return "\n\n".join(parts)
