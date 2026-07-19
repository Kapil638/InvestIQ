from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api.dependencies import get_research_ask_service
from app.core.config import Settings
from app.main import create_app
from app.schemas.ask import ResearchAskResponse


def test_ask_endpoint_returns_focused_answer() -> None:
    settings = Settings(app_env="test", debug=True, yfinance_enabled=True)
    app = create_app(settings=settings)

    mock_service = AsyncMock()
    mock_service.ask.return_value = ResearchAskResponse(
        ticker="INFY.NS",
        company_name="Infosys Limited",
        question="Explain the business model of this company",
        answer="Infosys is an IT services company focused on consulting and digital transformation.",
        generated_at=datetime.now(UTC),
        data_sources=["Yahoo Finance", "OpenRouter LLM"],
    )
    app.dependency_overrides[get_research_ask_service] = lambda: mock_service

    client = TestClient(app)
    response = client.post(
        f"{settings.api_prefix}/research/INFY/ask",
        json={"question": "Explain the business model of this company"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "INFY.NS"
    assert "Infosys" in data["answer"]
    mock_service.ask.assert_awaited_once_with(
        "INFY", "Explain the business model of this company"
    )


def test_ask_service_builds_answer() -> None:
    from app.schemas.financial import CompanyProfile, FinancialSummaryResponse
    from app.services.research_ask_service import ResearchAskService

    settings = Settings(app_env="test", debug=True, yfinance_enabled=True)
    financial = AsyncMock()
    financial.get_summary.return_value = FinancialSummaryResponse(
        ticker="INFY.NS",
        company_name="Infosys Limited",
        sector="Technology",
        industry="IT Services",
        market_cap=1e12,
        current_price=1500.0,
        currency="INR",
        pe_ratio=25.0,
        pb_ratio=8.0,
        roe=0.28,
        debt_to_equity=0.05,
        revenue_growth=0.1,
        profit_margin=0.18,
        dividend_yield=0.02,
        data_source="Yahoo Finance",
        data_timestamp=datetime.now(UTC),
    )
    financial.get_company_profile.return_value = CompanyProfile(
        symbol="INFY.NS",
        company_name="Infosys Limited",
        description="Global IT services and consulting firm.",
    )

    service = ResearchAskService(settings=settings, financial_service=financial)
    mock_llm = MagicMock()
    mock_llm.call.return_value = "Infosys earns revenue from IT consulting and outsourcing."

    with (
        patch.object(service, "_fetch_news_snippets", return_value=[]),
        patch("app.services.research_ask_service.build_llm", return_value=mock_llm),
    ):
        import asyncio

        result = asyncio.run(
            service.ask("INFY", "Explain the business model of this company")
        )

    assert "Infosys" in result.answer
    assert result.question.startswith("Explain the business model")
    mock_llm.call.assert_called_once()
