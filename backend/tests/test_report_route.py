from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_report_storage_service, get_research_crew_service
from app.core.config import Settings
from app.database.repositories.memory_repository import InMemoryReportRepository
from app.main import create_app
from app.schemas.financial import CompanyProfile, FinancialResearchResponse
from app.schemas.news import NewsResearchResponse
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
        news_data=NewsResearchResponse(ticker="AAPL"),
        financial_data_summary="Financial summary for AAPL",
        news_research_summary="News summary for AAPL",
        analysis="Detailed AAPL investment thesis with growth and valuation analysis.",
        guardrails=GuardrailResult(passed=True),
        recommendation=InvestmentRecommendation(
            rating=RecommendationRating.BUY,
            confidence_score=75.0,
            reasoning="Strong fundamentals",
        ),
        raw_recommendation="Rating: Buy\nConfidence Score: 75",
    )


def test_report_endpoint_returns_full_pipeline_output() -> None:
    settings = Settings(
        app_env="test",
        debug=True,
        yfinance_enabled=True,
        tavily_api_key="tavily-key",
        openrouter_api_key="openrouter-key",
        llm_provider="openrouter",
    )
    app = create_app(settings=settings)

    mock_service = MagicMock()
    mock_service.run = AsyncMock(return_value=_sample_report())
    app.dependency_overrides[get_research_crew_service] = lambda: mock_service
    app.dependency_overrides[get_report_storage_service] = lambda: ReportStorageService(
        repository=InMemoryReportRepository(),
        vector_store=None,
    )

    client = TestClient(app)
    response = client.post(f"{settings.api_prefix}/research/AAPL/report")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["id"] is not None
    assert data["recommendation"]["rating"] == "Buy"
    assert data["guardrails"]["passed"] is True
    mock_service.run.assert_awaited_once()
    assert mock_service.run.await_args.args[0] == "AAPL"
    assert "storage" in mock_service.run.await_args.kwargs


def test_report_endpoint_returns_503_without_openrouter_key() -> None:
    settings = Settings(
        app_env="test",
        debug=True,
        yfinance_enabled=True,
        tavily_api_key="tavily-key",
        openrouter_api_key=None,
    )
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.post(f"{settings.api_prefix}/research/AAPL/report")

    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]
