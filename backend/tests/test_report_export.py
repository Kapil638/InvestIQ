"""Tests for report PDF export and Google Drive save endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_report_export_service, get_report_storage_service
from app.core.config import Settings
from app.database.repositories.memory_repository import InMemoryReportRepository
from app.main import create_app
from app.schemas.financial import CompanyProfile, FinancialResearchResponse
from app.schemas.research import (
    GuardrailResult,
    InvestmentRecommendation,
    RecommendationRating,
    ResearchReportResponse,
)
from app.providers.google_drive_api_client import DriveUploadResult
from app.services.report_export_service import ReportExportService
from app.services.report_storage_service import ReportStorageService
from app.utils.exceptions import GoogleDriveNotConnectedError


@pytest.fixture
def storage_service() -> ReportStorageService:
    return ReportStorageService(
        repository=InMemoryReportRepository(),
        vector_store=None,
    )


@pytest.fixture
def sample_report() -> ResearchReportResponse:
    return ResearchReportResponse(
        ticker="INFY",
        generated_at=datetime(2026, 7, 6, tzinfo=UTC),
        financial_data=FinancialResearchResponse(
            ticker="INFY",
            profile=CompanyProfile(symbol="INFY", company_name="Infosys Limited"),
        ),
        financial_data_summary="Strong balance sheet with healthy margins.",
        news_research_summary="Recent earnings beat expectations.",
        analysis="Infosys shows steady growth with digital transformation tailwinds.",
        guardrails=GuardrailResult(passed=True),
        recommendation=InvestmentRecommendation(
            rating=RecommendationRating.BUY,
            confidence_score=78.0,
            reasoning="Solid fundamentals and reasonable valuation.",
            risks=["Currency headwinds", "Client concentration"],
            investment_horizon="3+ years",
        ),
        confidence_score=78,
    )


@pytest.fixture
def client(storage_service: ReportStorageService) -> TestClient:
    settings = Settings(app_env="test", debug=True, chroma_enabled=False)
    app = create_app(settings=settings)
    app.dependency_overrides[get_report_storage_service] = lambda: storage_service
    return TestClient(app)


def _export_service(storage_service: ReportStorageService) -> ReportExportService:
    from app.services.google_drive_service import GoogleDriveService

    settings = Settings(app_env="test", debug=True)
    return ReportExportService(
        storage=storage_service,
        drive_service=GoogleDriveService(settings=settings),
    )


@pytest.mark.asyncio
async def test_pdf_endpoint_returns_application_pdf(
    client: TestClient,
    storage_service: ReportStorageService,
    sample_report: ResearchReportResponse,
) -> None:
    stored = await storage_service.save(sample_report)
    export_service = _export_service(storage_service)
    client.app.dependency_overrides[get_report_export_service] = lambda: export_service

    response = client.post(f"/api/v1/reports/{stored.id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 500
    disposition = response.headers.get("content-disposition", "")
    assert "INFY" in disposition
    assert disposition.endswith('.pdf"') or ".pdf" in disposition


@pytest.mark.asyncio
async def test_pdf_endpoint_records_pdf_generated_at(
    client: TestClient,
    storage_service: ReportStorageService,
    sample_report: ResearchReportResponse,
) -> None:
    stored = await storage_service.save(sample_report)
    export_service = _export_service(storage_service)
    client.app.dependency_overrides[get_report_export_service] = lambda: export_service

    client.post(f"/api/v1/reports/{stored.id}/pdf")

    updated = await storage_service.get(stored.id)
    assert updated is not None
    assert updated.pdf_generated_at is not None


@pytest.mark.asyncio
async def test_drive_endpoint_handles_missing_google_drive_config(
    client: TestClient,
    storage_service: ReportStorageService,
    sample_report: ResearchReportResponse,
) -> None:
    stored = await storage_service.save(sample_report)
    export_service = _export_service(storage_service)
    client.app.dependency_overrides[get_report_export_service] = lambda: export_service

    response = client.post(f"/api/v1/reports/{stored.id}/drive")

    assert response.status_code == 503
    assert response.json()["detail"] == "Google Drive is not connected."


@pytest.mark.asyncio
async def test_drive_endpoint_saves_metadata(
    client: TestClient,
    storage_service: ReportStorageService,
    sample_report: ResearchReportResponse,
) -> None:
    stored = await storage_service.save(sample_report)
    export_service = _export_service(storage_service)
    client.app.dependency_overrides[get_report_export_service] = lambda: export_service

    with patch.object(
        export_service._drive,
        "upload_report_pdf",
        new=AsyncMock(
            return_value=DriveUploadResult(
                file_id="drive-file-123",
                url="https://drive.google.com/file/d/abc/view",
            )
        ),
    ):
        response = client.post(f"/api/v1/reports/{stored.id}/drive")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["drive_file_id"] == "drive-file-123"
    assert body["drive_url"] == "https://drive.google.com/file/d/abc/view"

    updated = await storage_service.get(stored.id)
    assert updated is not None
    assert updated.google_drive_file_id == "drive-file-123"
    assert updated.google_drive_url == "https://drive.google.com/file/d/abc/view"
    assert updated.google_drive_saved_at is not None
    assert updated.pdf_generated_at is not None


def test_google_drive_not_connected_message() -> None:
    settings = Settings(google_drive_enabled=False)
    from app.providers.google_drive_api_client import GoogleDriveApiClient

    client = GoogleDriveApiClient(settings)
    with pytest.raises(GoogleDriveNotConnectedError, match="Google Drive is not connected."):
        client.assert_enabled()


def test_google_drive_not_connected_without_credentials() -> None:
    settings = Settings(google_drive_enabled=True)
    from app.providers.google_drive_api_client import GoogleDriveApiClient

    client = GoogleDriveApiClient(settings)
    with pytest.raises(GoogleDriveNotConnectedError, match="Google Drive is not connected."):
        client.assert_enabled()
