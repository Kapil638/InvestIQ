"""Regression tests for intent-driven advisor workflow."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils import ttl_cache
from app.core.config import Settings
from app.schemas.advisor import AdvisorRecommendRequest, CandidateValidation, InvestorProfile, StockRecommendation, ThemeIntent
from app.schemas.company_search import CompanySearchResponse, CompanySearchResult
from app.schemas.financial import FinancialSummaryResponse
from app.services.advisor_intent_service import AdvisorIntentService, AdvisorIntentType, ClassifiedIntent
from app.services.advisor_guardrails import apply_guardrails as guardrails_fn
from app.services.advisor_service import AdvisorService


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    ttl_cache.clear_all()
    yield
    ttl_cache.clear_all()


def test_market_prompt_classified_correctly() -> None:
    from app.services.advisor_intent_service import _classify_rule_based

    result = _classify_rule_based("can you list out top 5 best company to invest in 2026")
    assert result == AdvisorIntentType.MARKET_RECOMMENDATION


def test_theme_prompt_classified_correctly() -> None:
    from app.services.advisor_intent_service import _classify_rule_based

    assert _classify_rule_based("Best AI and defence stocks") == AdvisorIntentType.THEME_DISCOVERY


def test_personalized_prompt_classified_correctly() -> None:
    from app.services.advisor_intent_service import _classify_rule_based

    result = _classify_rule_based("I have ₹5 lakh to invest for 3 years moderate risk")
    assert result == AdvisorIntentType.PERSONALIZED_PORTFOLIO


def test_build_profile_keeps_null_when_not_stated() -> None:
    from app.services.advisor_intent_service import _build_profile

    profile, themes, user_fields = _build_profile(
        {
            "capital": None,
            "time_horizon": None,
            "risk_appetite": None,
            "preferences": [],
            "avoidances": [],
            "themes": [],
        },
        AdvisorIntentType.MARKET_RECOMMENDATION,
    )
    assert profile.capital is None
    assert profile.risk_appetite is None
    assert profile.preferences == []
    assert profile.avoidances == []
    assert themes == []
    assert user_fields == []


@pytest.mark.asyncio
async def test_market_recommendation_no_hallucinated_profile() -> None:
    settings = Settings(app_env="test", yfinance_enabled=True, openrouter_api_key="key")
    financial = AsyncMock()
    financial.get_summary.return_value = FinancialSummaryResponse(
        ticker="INFY.NS",
        company_name="Infosys Ltd",
        sector="IT",
        industry="IT",
        market_cap=1e12,
        current_price=1500.0,
        currency="INR",
        pe_ratio=22.0,
        pb_ratio=8.0,
        roe=0.25,
        debt_to_equity=0.05,
        revenue_growth=0.1,
        profit_margin=0.18,
        dividend_yield=0.02,
        data_source="yahoo",
        data_timestamp=datetime.now(UTC),
    )
    search = AsyncMock()
    search.search.return_value = CompanySearchResponse(
        results=[
            CompanySearchResult(
                symbol="INFY", company_name="Infosys", exchange="NSE", sector="IT", source="yahoo"
            ),
            CompanySearchResult(
                symbol="TCS", company_name="TCS", exchange="NSE", sector="IT", source="yahoo"
            ),
        ],
        source="yahoo",
    )

    service = AdvisorService(settings=settings, financial_service=financial, search_service=search)

    from app.services.advisor_intent_service import ClassifiedIntent, MARKET_ASSUMPTIONS

    classified = ClassifiedIntent(
        intent=AdvisorIntentType.MARKET_RECOMMENDATION,
        profile=InvestorProfile(),
        search_queries=["large cap quality NSE India"],
        assumptions_used=list(MARKET_ASSUMPTIONS),
        missing_inputs=["capital", "time_horizon", "risk_appetite"],
    )

    rank_json = (
        '{"recommendations":[{"rank":1,"symbol":"INFY","company_name":"Infosys","sector":"IT",'
        '"suggested_allocation_percent":50,"why_it_fits":["quality name"],"key_risks":["market"],'
        '"theme_match_reason":"quality screen"},{"rank":2,"symbol":"TCS","company_name":"TCS",'
        '"sector":"IT","suggested_allocation_percent":50,"why_it_fits":["quality"],"key_risks":["risk"],'
        '"theme_match_reason":"quality"}],"portfolio_mix":{"large_cap_percent":80,"mid_cap_percent":20,'
        '"small_cap_percent":0,"risk_summary":"balanced","time_horizon_suitability":"long term"}}'
    )
    mock_llm = MagicMock()
    mock_llm.call.return_value = rank_json

    with (
        patch.object(service._intent_service, "classify", AsyncMock(return_value=classified)),
        patch("app.services.advisor_service.build_llm", return_value=mock_llm),
        patch("app.services.advisor_service.call_llm_with_retry", side_effect=lambda llm, p, **_: llm.call(p)),
    ):
        result = await service.recommend(
            AdvisorRecommendRequest(
                prompt="can you list out top 5 best company to invest in 2026"
            )
        )

    assert result.intent == "MARKET_RECOMMENDATION"
    assert result.investor_profile.capital is None
    assert result.investor_profile.risk_appetite is None
    assert result.investor_profile.preferences == []
    assert result.assumptions_used
    assert len(result.recommendations) >= 1


@pytest.mark.asyncio
async def test_empty_retrieval_returns_clarification() -> None:
    settings = Settings(app_env="test", yfinance_enabled=True)
    service = AdvisorService(
        settings=settings,
        financial_service=AsyncMock(),
        search_service=AsyncMock(),
    )
    from app.services.advisor_intent_service import ClassifiedIntent

    classified = ClassifiedIntent(
        intent=AdvisorIntentType.THEME_DISCOVERY,
        profile=InvestorProfile(),
        themes=[ThemeIntent(name="AI", keywords=["ai"])],
        search_queries=["ai stock"],
        theme_keywords=["ai"],
    )

    with (
        patch.object(service._intent_service, "classify", AsyncMock(return_value=classified)),
        patch.object(service._retrieval, "retrieve_with_fallback", AsyncMock(return_value=([], []))),
    ):
        result = await service.recommend(
            AdvisorRecommendRequest(prompt="Best AI stocks for research please now")
        )

    assert result.clarification_message is not None
    assert result.recommendations == []
    assert result.warning is not None


def test_guardrails_block_unknown_ticker() -> None:
    validations = {
        "INFY": CandidateValidation(
            symbol="INFY",
            is_valid=True,
            matched_themes=["market quality"],
            theme_match_score=80,
            evidence=["IT sector"],
            reason="ok",
        )
    }
    recs = [
        StockRecommendation(
            rank=1,
            symbol="FAKECO",
            company_name="Fake",
            sector="X",
            match_score=90,
            overall_match_score=90,
            theme_match_score=90,
            matched_themes=["market quality"],
            theme_match_reason="x",
            key_evidence=["e"],
            suggested_allocation_percent=100,
            why_it_fits=["x"],
            key_risks=["r"],
            data_sources=["yahoo"],
        )
    ]
    out = guardrails_fn(recs, validations, {"INFY"}, require_themes=False)
    assert out == []
