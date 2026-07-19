"""Report repository interface."""

from typing import Protocol

from app.models.research_report import StoredResearchReport
from app.schemas.research import ResearchReportResponse
from app.schemas.storage import ReportSummary


class ReportRepository(Protocol):
    async def save(self, report: ResearchReportResponse) -> StoredResearchReport: ...

    async def get_by_id(self, report_id: str) -> StoredResearchReport | None: ...

    async def list_reports(
        self,
        *,
        ticker: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ReportSummary], int]: ...

    async def delete(self, report_id: str) -> bool: ...
