"""Tests for AI Investment Advisor endpoint."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_advisor_service
from app.core.config import Settings
from app.main import create_app
from app.schemas.advisor import (
    ADVISOR_DISCLAIMER,
    AdvisorRecommendResponse,
    AdvisorRetrievalSummary,
    InvestorProfile,
    PortfolioMix,
    ProfileFieldDisplay,
    StockRecommendation,
)
from app.services.advisor_utils import extract_json
from app.utils import ttl_cache


@pytest.fixture(autouse=True)
def clear_advisor_cache() -> None:
    ttl_cache.clear_all()
    yield
    ttl_cache.clear_all()


def _sample_response() -> AdvisorRecommendResponse:
    return AdvisorRecommendResponse(
        intent="MARKET_RECOMMENDATION",
        investor_profile=InvestorProfile(),
        profile_fields=[
            ProfileFieldDisplay(label="Mode", value="Market recommendation", source="assumed")
        ],
        recommendations=[
            StockRecommendation(
                rank=1,
                symbol="BEL",
                company_name="Bharat Electronics Ltd",
                sector="Defence",
                match_score=87,
                overall_match_score=87,
                theme_match_score=85,
                matched_themes=["market quality"],
                theme_match_reason="Quality screen",
                key_evidence=["Defence electronics segment"],
                suggested_allocation_percent=20,
                why_it_fits=["May be suitable for thematic research."],
                key_risks=["Order book concentration"],
                data_sources=["yahoo"],
            )
        ],
        portfolio_mix=PortfolioMix(
            large_cap_percent=60,
            mid_cap_percent=30,
            small_cap_percent=10,
            risk_summary="Moderate thematic tilt.",
            time_horizon_suitability="3-year horizon",
        ),
        disclaimer=ADVISOR_DISCLAIMER,
        assumptions_used=["Balanced long-term research lens."],
        retrieval_summary=AdvisorRetrievalSummary(
            raw_candidates_count=10,
            validated_candidates_count=5,
            providers_used=["yahoo"],
        ),
    )


def test_extract_json_strips_markdown_fence() -> None:
    raw = '```json\n{"capital": "₹5 lakh", "preferences": ["dividend"]}\n```'
    parsed = extract_json(raw)
    assert isinstance(parsed, dict)
    assert parsed["capital"] == "₹5 lakh"


def test_advisor_endpoint_response_schema() -> None:
    settings = Settings(app_env="test", debug=True, yfinance_enabled=True)
    app = create_app(settings=settings)
    mock_service = AsyncMock()
    mock_service.recommend.return_value = _sample_response()
    app.dependency_overrides[get_advisor_service] = lambda: mock_service

    client = TestClient(app)
    response = client.post(
        f"{settings.api_prefix}/advisor/recommend",
        json={"prompt": "can you list out top 5 best company to invest in 2026"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "MARKET_RECOMMENDATION"
    assert data["recommendations"][0]["symbol"] == "BEL"
    assert data["disclaimer"] == ADVISOR_DISCLAIMER
    mock_service.recommend.assert_awaited_once()
