from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_rag_service,
    get_report_chat_service,
    get_report_storage_service,
    get_research_crew_service,
)
from app.core.config import Settings
from app.database.repositories.memory_repository import InMemoryReportRepository
from app.main import create_app
from app.schemas.chat import ChatTurn
from app.schemas.financial import CompanyProfile, FinancialResearchResponse
from app.schemas.storage import SimilarReportMatch, SimilarReportsResponse
from app.schemas.research import (
    GuardrailResult,
    InvestmentRecommendation,
    RecommendationRating,
    ResearchReportResponse,
)
from app.services.rag_service import RagService
from app.services.report_chat_service import ReportChatService
from app.services.report_storage_service import ReportStorageService
from app.utils import ttl_cache


def _sample_report(*, ticker: str = "INFY") -> ResearchReportResponse:
    return ResearchReportResponse(
        ticker=ticker,
        generated_at=datetime.now(UTC),
        financial_data=FinancialResearchResponse(
            ticker=ticker,
            profile=CompanyProfile(
                symbol=ticker,
                company_name="Infosys Limited",
                sector="Technology",
                industry="IT Services",
                description="Global IT consulting and services company.",
            ),
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
    )


@pytest.fixture
def storage_service() -> ReportStorageService:
    return ReportStorageService(
        repository=InMemoryReportRepository(),
        vector_store=None,
    )


@pytest.fixture
def client(storage_service: ReportStorageService) -> TestClient:
    settings = Settings(
        app_env="test",
        debug=True,
        rag_enabled=False,
        openrouter_api_key="test-openrouter-key",
    )
    app = create_app(settings=settings)
    app.dependency_overrides[get_report_storage_service] = lambda: storage_service
    app.dependency_overrides[get_rag_service] = lambda: RagService(vector_store=None)
    return TestClient(app)


@pytest.mark.asyncio
async def test_report_chat_includes_prior_conversation_in_prompt(
    storage_service: ReportStorageService,
) -> None:
    stored = await storage_service.save(_sample_report())

    with patch("app.services.report_chat_service.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.call.return_value = "That P/E ratio is elevated relative to peers."
        mock_build.return_value = mock_llm

        chat_service = ReportChatService(
            settings=Settings(openrouter_api_key="key"),
            storage=storage_service,
            rag_service=None,
        )
        history = [
            ChatTurn(role="user", content="What is the P/E ratio?"),
            ChatTurn(role="assistant", content="The report cites a P/E of 28x."),
        ]
        await chat_service.chat(stored.id, "Is that high?", history=history)

    prompt = mock_llm.call.call_args[0][0]
    assert "PRIOR CONVERSATION:" in prompt
    assert "User: What is the P/E ratio?" in prompt
    assert "Assistant: The report cites a P/E of 28x." in prompt
    assert "USER QUESTION:\nIs that high?" in prompt


@pytest.mark.asyncio
async def test_report_chat_rag_search_runs_per_question(
    storage_service: ReportStorageService,
) -> None:
    stored = await storage_service.save(_sample_report())
    rag_match = SimilarReportMatch(
        report_id="other-report-id",
        ticker="INFY",
        snippet="Peer valuation context.",
        relevance_score=0.82,
    )

    mock_rag = MagicMock(spec=RagService)
    mock_rag.is_enabled = True
    mock_rag.search_similar = AsyncMock(
        side_effect=[
            SimilarReportsResponse(query="valuation", results=[rag_match]),
            SimilarReportsResponse(query="risks", results=[rag_match]),
        ]
    )

    chat_service = ReportChatService(
        settings=Settings(openrouter_api_key="key", cache_enabled=True),
        storage=storage_service,
        rag_service=mock_rag,
    )

    ttl_cache.clear_all()
    with patch("app.services.report_chat_service.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.call.return_value = "Answer."
        mock_build.return_value = mock_llm

        with patch("app.utils.ttl_cache._enabled", return_value=True):
            await chat_service.chat(stored.id, "What is the valuation?")
            await chat_service.chat(stored.id, "What are the main risks?")

    assert mock_rag.search_similar.await_count == 2
    assert mock_rag.search_similar.await_args_list[0].args[0] == "What is the valuation?"
    assert mock_rag.search_similar.await_args_list[1].args[0] == "What are the main risks?"


@pytest.mark.asyncio
async def test_report_chat_returns_answer_when_report_exists(
    client: TestClient, storage_service: ReportStorageService
) -> None:
    stored = await storage_service.save(_sample_report())

    with patch("app.services.report_chat_service.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.call.return_value = "The biggest risks are currency headwinds and client concentration."
        mock_build.return_value = mock_llm

        chat_service = ReportChatService(
            settings=Settings(openrouter_api_key="key"),
            storage=storage_service,
            rag_service=None,
        )
        client.app.dependency_overrides[get_report_chat_service] = lambda: chat_service

        response = client.post(
            f"/api/v1/reports/{stored.id}/chat",
            json={"question": "What are the key risks?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["report_id"] == stored.id
    assert "currency headwinds" in data["answer"].lower()
    assert "Stored report" in data["sources"]
    mock_llm.call.assert_called_once()


def test_report_chat_not_found(client: TestClient) -> None:
    chat_service = ReportChatService(
        settings=Settings(openrouter_api_key="key"),
        storage=ReportStorageService(InMemoryReportRepository(), None),
        rag_service=None,
    )
    client.app.dependency_overrides[get_report_chat_service] = lambda: chat_service

    response = client.post(
        "/api/v1/reports/missing-report-id/chat",
        json={"question": "What are the key risks?"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_report_chat_does_not_trigger_crewai_pipeline(
    client: TestClient, storage_service: ReportStorageService
) -> None:
    stored = await storage_service.save(_sample_report())

    mock_crew = MagicMock()
    mock_crew.run = AsyncMock(return_value=_sample_report())

    with patch("app.services.report_chat_service.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.call.return_value = "Buy rating reflects solid fundamentals."
        mock_build.return_value = mock_llm

        chat_service = ReportChatService(
            settings=Settings(openrouter_api_key="key"),
            storage=storage_service,
        )
        client.app.dependency_overrides[get_research_crew_service] = lambda: mock_crew
        client.app.dependency_overrides[get_report_chat_service] = lambda: chat_service

        response = client.post(
            f"/api/v1/reports/{stored.id}/chat",
            json={"question": "Why is this stock a Buy?"},
        )

    assert response.status_code == 200
    mock_crew.run.assert_not_called()


@pytest.mark.asyncio
async def test_report_retrieval_from_storage(
    client: TestClient, storage_service: ReportStorageService
) -> None:
    stored = await storage_service.save(_sample_report(ticker="TCS"))

    response = client.get(f"/api/v1/reports/{stored.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "TCS"
    assert data["rating"] == "BUY"
    assert data["confidence_score"] == 78.0
    assert data["report"]["analysis"] is not None


def test_existing_report_generation_still_works() -> None:
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
    mock_service.run = AsyncMock(return_value=_sample_report(ticker="AAPL"))
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
    assert data["recommendation"]["rating"] == "Buy"
    mock_service.run.assert_awaited_once()
    assert mock_service.run.await_args.args[0] == "AAPL"
    assert "storage" in mock_service.run.await_args.kwargs
