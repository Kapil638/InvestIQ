from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_rag_service, get_report_storage_service
from app.core.config import Settings
from app.database.repositories.memory_repository import InMemoryReportRepository
from app.main import create_app
from app.schemas.financial import CompanyProfile, FinancialResearchResponse
from app.schemas.research import ResearchReportResponse
from app.services.rag_service import RagService
from app.services.report_storage_service import ReportStorageService


@pytest.fixture
def storage_service() -> ReportStorageService:
    return ReportStorageService(
        repository=InMemoryReportRepository(),
        vector_store=None,
    )


@pytest.fixture
def client(storage_service: ReportStorageService) -> TestClient:
    settings = Settings(app_env="test", debug=True, rag_enabled=False)
    app = create_app(settings=settings)
    app.dependency_overrides[get_report_storage_service] = lambda: storage_service
    app.dependency_overrides[get_rag_service] = lambda: RagService(vector_store=None)
    return TestClient(app)


def test_list_reports_empty(client: TestClient) -> None:
    response = client.get("/api/v1/reports")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_get_report_by_id(client: TestClient, storage_service: ReportStorageService) -> None:
    report = ResearchReportResponse(
        ticker="AAPL",
        generated_at=datetime.now(UTC),
        financial_data=FinancialResearchResponse(
            ticker="AAPL",
            profile=CompanyProfile(symbol="AAPL", company_name="Apple Inc."),
        ),
    )
    stored = await storage_service.save(report)

    response = client.get(f"/api/v1/reports/{stored.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == stored.id
    assert data["ticker"] == "AAPL"


def test_get_report_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/reports/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_reports_by_ticker(
    client: TestClient, storage_service: ReportStorageService
) -> None:
    await storage_service.save(
        ResearchReportResponse(
            ticker="AAPL",
            financial_data=FinancialResearchResponse(
                ticker="AAPL",
                profile=CompanyProfile(symbol="AAPL", company_name="Apple Inc."),
            ),
        )
    )
    await storage_service.save(
        ResearchReportResponse(
            ticker="MSFT",
            financial_data=FinancialResearchResponse(
                ticker="MSFT",
                profile=CompanyProfile(symbol="MSFT", company_name="Microsoft"),
            ),
        )
    )

    response = client.get("/api/v1/reports/ticker/AAPL")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_delete_report(client: TestClient, storage_service: ReportStorageService) -> None:
    stored = await storage_service.save(
        ResearchReportResponse(
            ticker="AAPL",
            financial_data=FinancialResearchResponse(
                ticker="AAPL",
                profile=CompanyProfile(symbol="AAPL", company_name="Apple Inc."),
            ),
        )
    )

    response = client.delete(f"/api/v1/reports/{stored.id}")

    assert response.status_code == 204
    assert await storage_service.get(stored.id) is None


@pytest.mark.asyncio
async def test_bulk_delete_reports(client: TestClient, storage_service: ReportStorageService) -> None:
    first = await storage_service.save(
        ResearchReportResponse(
            ticker="AAPL",
            financial_data=FinancialResearchResponse(
                ticker="AAPL",
                profile=CompanyProfile(symbol="AAPL", company_name="Apple Inc."),
            ),
        )
    )
    second = await storage_service.save(
        ResearchReportResponse(
            ticker="MSFT",
            financial_data=FinancialResearchResponse(
                ticker="MSFT",
                profile=CompanyProfile(symbol="MSFT", company_name="Microsoft"),
            ),
        )
    )

    response = client.post(
        "/api/v1/reports/bulk-delete",
        json={"report_ids": [first.id, second.id, "missing-id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["deleted"] == 2
    assert body["not_found"] == ["missing-id"]
    assert await storage_service.get(first.id) is None
    assert await storage_service.get(second.id) is None


def test_similar_search_disabled_without_chroma(client: TestClient) -> None:
    response = client.get("/api/v1/reports/search/similar", params={"query": "apple growth"})
    assert response.status_code == 503
