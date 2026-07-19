from datetime import UTC, datetime

import pytest

from app.database.repositories.memory_repository import InMemoryReportRepository
from app.schemas.financial import CompanyProfile, FinancialResearchResponse
from app.schemas.research import (
    GuardrailResult,
    InvestmentRecommendation,
    RecommendationRating,
    ResearchReportResponse,
)
from app.services.report_storage_service import ReportStorageService


def _sample_report() -> ResearchReportResponse:
    return ResearchReportResponse(
        ticker="AAPL",
        generated_at=datetime.now(UTC),
        financial_data=FinancialResearchResponse(
            ticker="AAPL",
            profile=CompanyProfile(symbol="AAPL", company_name="Apple Inc."),
        ),
        analysis="AAPL analysis with growth, valuation, and risk factors considered.",
        guardrails=GuardrailResult(passed=True),
        recommendation=InvestmentRecommendation(
            rating=RecommendationRating.BUY,
            confidence_score=80.0,
            reasoning="Strong fundamentals",
        ),
    )


@pytest.fixture
def storage_service() -> ReportStorageService:
    return ReportStorageService(
        repository=InMemoryReportRepository(),
        vector_store=None,
    )


@pytest.mark.asyncio
async def test_save_assigns_id_and_persists(storage_service: ReportStorageService) -> None:
    stored = await storage_service.save(_sample_report())

    assert stored.id is not None
    assert stored.ticker == "AAPL"
    assert stored.company_name == "Apple Inc."
    assert stored.rating == "BUY"
    assert stored.report.id == stored.id


@pytest.mark.asyncio
async def test_get_by_id_returns_stored_report(storage_service: ReportStorageService) -> None:
    stored = await storage_service.save(_sample_report())

    fetched = await storage_service.get(stored.id)

    assert fetched is not None
    assert fetched.id == stored.id
    assert fetched.report.ticker == "AAPL"


@pytest.mark.asyncio
async def test_list_reports_filters_by_ticker(storage_service: ReportStorageService) -> None:
    await storage_service.save(_sample_report())
    await storage_service.save(_sample_report().model_copy(update={"ticker": "MSFT"}))

    items, total = await storage_service.list_reports(ticker="AAPL")

    assert total == 1
    assert items[0].ticker == "AAPL"


@pytest.mark.asyncio
async def test_delete_removes_report(storage_service: ReportStorageService) -> None:
    stored = await storage_service.save(_sample_report())

    deleted = await storage_service.delete(stored.id)
    fetched = await storage_service.get(stored.id)

    assert deleted is True
    assert fetched is None
