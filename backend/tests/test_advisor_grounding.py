"""Tests for grounded advisor retrieval, validation, and guardrails."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.schemas.advisor import (
    AdvisorRecommendRequest,
    CandidateValidation,
    InvestorProfile,
    RawCandidate,
    StockRecommendation,
    ThemeIntent,
    THEME_MATCH_THRESHOLD,
)
from app.schemas.company_search import CompanySearchResponse, CompanySearchResult
from app.schemas.financial import FinancialSummaryResponse
from app.services.advisor_guardrails import apply_guardrails
from app.services.advisor_retrieval import AdvisorRetrieval
from app.services.advisor_scoring import rule_theme_score
from app.services.advisor_service import AdvisorService, _build_recommendations_from_rank
from app.services.advisor_intent_service import ClassifiedIntent, AdvisorIntentType
from app.services.advisor_validation import AdvisorValidator, EnrichedCandidate
from app.services.advisor_utils import extract_json
from app.utils import ttl_cache


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    ttl_cache.clear_all()
    yield
    ttl_cache.clear_all()


def _defence_theme_profile() -> InvestorProfile:
    return InvestorProfile(
        capital="₹5 lakh",
        time_horizon="3 years",
        risk_appetite="moderate",
        themes=[
            ThemeIntent(
                name="AI and Defence",
                keywords=["ai", "artificial intelligence", "defence", "defense", "aerospace", "radar"],
                related_sectors=["Defence", "Aerospace", "Technology"],
                inclusion_criteria="Meaningful defence or AI exposure",
                exclusion_criteria="Generic bank/FMCG without theme exposure",
            )
        ],
        avoidances=[],
    )


def _financial(symbol: str, sector: str, company: str) -> FinancialSummaryResponse:
    return FinancialSummaryResponse(
        ticker=f"{symbol}.NS",
        company_name=company,
        sector=sector,
        industry=sector,
        market_cap=1e11,
        current_price=1000.0,
        currency="INR",
        pe_ratio=22.0,
        pb_ratio=4.0,
        roe=0.2,
        debt_to_equity=0.3,
        revenue_growth=0.1,
        profit_margin=0.15,
        dividend_yield=0.01,
        data_source="yahoo",
        data_timestamp=datetime.now(UTC),
    )


def test_rule_theme_rejects_unrelated_bank() -> None:
    blob = "hdfc bank ltd financial services banking"
    score, _, evidence = rule_theme_score(
        blob,
        ["defence", "aerospace", "radar"],
        ["Defence", "Aerospace"],
        "Generic bank without defence exposure",
    )
    assert score < THEME_MATCH_THRESHOLD
    assert not evidence or score < 60


def test_rule_theme_accepts_defence_company() -> None:
    blob = "bharat electronics ltd defence electronics radar aerospace"
    score, matched, evidence = rule_theme_score(
        blob,
        ["defence", "radar", "aerospace"],
        ["Defence", "Aerospace"],
        "Generic industrial without defence",
    )
    assert score >= THEME_MATCH_THRESHOLD
    assert evidence


def test_guardrails_reject_unknown_ticker() -> None:
    validations = {
        "BEL": CandidateValidation(
            symbol="BEL",
            is_valid=True,
            matched_themes=["Defence"],
            theme_match_score=85,
            evidence=["Defence electronics exposure"],
            reason="Defence theme match",
        )
    }
    recs = [
        StockRecommendation(
            rank=1,
            symbol="HDFCBANK",
            company_name="HDFC Bank",
            sector="Financial Services",
            match_score=90,
            overall_match_score=90,
            theme_match_score=90,
            matched_themes=["Defence"],
            theme_match_reason="invalid",
            key_evidence=["x"],
            suggested_allocation_percent=100,
            why_it_fits=["test"],
            key_risks=["risk"],
            data_sources=["yahoo"],
        )
    ]
    filtered = apply_guardrails(recs, validations, {"BEL"})
    assert filtered == []


def test_guardrails_reject_low_theme_score() -> None:
    validations = {
        "ITC": CandidateValidation(
            symbol="ITC",
            is_valid=False,
            matched_themes=["FMCG"],
            theme_match_score=40,
            evidence=["consumer"],
            reason="weak",
            reject_reason="low score",
        )
    }
    recs = [
        StockRecommendation(
            rank=1,
            symbol="ITC",
            company_name="ITC",
            sector="FMCG",
            match_score=40,
            overall_match_score=40,
            theme_match_score=40,
            matched_themes=["FMCG"],
            theme_match_reason="weak",
            key_evidence=["consumer"],
            suggested_allocation_percent=100,
            why_it_fits=["test"],
            key_risks=["risk"],
            data_sources=["yahoo"],
        )
    ]
    assert apply_guardrails(recs, validations, {"ITC"}) == []


def test_rank_cannot_inject_unknown_ticker() -> None:
    validated = [
        EnrichedCandidate(
            raw=RawCandidate(
                symbol="BEL",
                company_name="Bharat Electronics",
                exchange="NSE",
                sector="Defence",
                source="tapetide_mcp",
            ),
            snapshot=_financial("BEL", "Defence", "Bharat Electronics"),
        )
    ]
    validation_map = {
        "BEL": CandidateValidation(
            symbol="BEL",
            is_valid=True,
            matched_themes=["Defence"],
            theme_match_score=88,
            evidence=["Defence electronics"],
            reason="Defence exposure",
        )
    }
    parsed = {
        "recommendations": [
            {
                "rank": 1,
                "symbol": "HDFCBANK",
                "company_name": "HDFC Bank",
                "sector": "Banking",
                "suggested_allocation_percent": 100,
                "why_it_fits": ["should not appear"],
                "key_risks": ["risk"],
                "theme_match_reason": "hallucinated",
            },
            {
                "rank": 2,
                "symbol": "BEL",
                "company_name": "Bharat Electronics",
                "sector": "Defence",
                "suggested_allocation_percent": 100,
                "why_it_fits": ["defence exposure"],
                "key_risks": ["order book risk"],
                "theme_match_reason": "Defence electronics",
            },
        ]
    }
    recs = _build_recommendations_from_rank(parsed, validated, validation_map)
    assert len(recs) == 1
    assert recs[0].symbol == "BEL"


@pytest.mark.asyncio
async def test_retrieval_fallback_when_tapetide_unavailable() -> None:
    search = AsyncMock()
    search.search.side_effect = [
        Exception("mcp down"),
        CompanySearchResponse(
            results=[
                CompanySearchResult(
                    symbol="BEL",
                    company_name="Bharat Electronics",
                    exchange="NSE",
                    sector="Defence",
                    source="local_master",
                )
            ],
            source="local_master",
        ),
    ]
    retrieval = AdvisorRetrieval(search, tavily_api_key=None)
    profile = _defence_theme_profile()
    results = await retrieval.retrieve(profile, ["defence electronics india"], ["defence"])
    assert any(r.symbol == "BEL" for r in results)


@pytest.mark.asyncio
async def test_no_validated_candidates_returns_broaden_warning() -> None:
    settings = Settings(app_env="test", yfinance_enabled=True)
    service = AdvisorService(
        settings=settings,
        financial_service=AsyncMock(),
        search_service=AsyncMock(),
    )
    classified = ClassifiedIntent(
        intent=AdvisorIntentType.THEME_DISCOVERY,
        profile=_defence_theme_profile(),
        themes=_defence_theme_profile().themes,
        search_queries=["defence"],
        theme_keywords=["defence"],
    )

    with (
        patch.object(service._intent_service, "classify", AsyncMock(return_value=classified)),
        patch.object(service._retrieval, "retrieve_with_fallback", AsyncMock(return_value=([], []))),
    ):
        result = await service.recommend(
            AdvisorRecommendRequest(
                prompt="I want AI and defence stocks for 3 years with moderate risk."
            )
        )

    assert result.recommendations == []
    assert result.clarification_message is not None
    assert any(
        phrase in result.clarification_message.lower()
        for phrase in ("broaden", "broader", "could not retrieve")
    )


@pytest.mark.asyncio
async def test_advisor_does_not_use_crewai() -> None:
    from app.services import advisor_service as mod

    text = open(mod.__file__, encoding="utf-8").read()
    assert "ResearchCrewService" not in text
    assert "Crew(" not in text


def test_advisor_no_trading_tools() -> None:
    from app.services import advisor_service as mod

    text = open(mod.__file__, encoding="utf-8").read()
    assert "place_order" not in text


@pytest.mark.asyncio
async def test_validation_requires_evidence_and_matched_themes() -> None:
    settings = Settings(app_env="test", openrouter_api_key="key", yfinance_enabled=True)
    validator = AdvisorValidator(settings)
    profile = _defence_theme_profile()

    enriched = [
        EnrichedCandidate(
            raw=RawCandidate(
                symbol="BEL",
                company_name="Bharat Electronics Ltd",
                exchange="NSE",
                sector="Defence Electronics",
                source="tapetide_mcp",
            ),
            industry="Defence Electronics",
            business_summary="Defence electronics and radar systems",
            snapshot=_financial("BEL", "Defence", "Bharat Electronics Ltd"),
        ),
        EnrichedCandidate(
            raw=RawCandidate(
                symbol="ITC",
                company_name="ITC Ltd",
                exchange="NSE",
                sector="Consumer Goods",
                source="yahoo",
            ),
            industry="FMCG",
            snapshot=_financial("ITC", "Consumer Goods", "ITC Ltd"),
        ),
    ]

    llm_json = [
        {
            "symbol": "BEL",
            "is_valid": True,
            "matched_themes": ["AI and Defence"],
            "theme_match_score": 85,
            "evidence": ["Defence electronics segment"],
            "reason": "Defence electronics exposure",
        },
        {
            "symbol": "ITC",
            "is_valid": False,
            "matched_themes": [],
            "theme_match_score": 20,
            "evidence": [],
            "reason": "",
            "reject_reason": "FMCG not defence/AI",
        },
    ]

    with patch.object(validator, "_llm_validate_batch", AsyncMock(return_value={
        "BEL": CandidateValidation(
            symbol="BEL",
            is_valid=True,
            matched_themes=["AI and Defence"],
            theme_match_score=85,
            evidence=["Defence electronics segment"],
            reason="Defence electronics exposure",
        ),
        "ITC": CandidateValidation(
            symbol="ITC",
            is_valid=False,
            matched_themes=[],
            theme_match_score=20,
            evidence=[],
            reason="",
            reject_reason="FMCG not defence/AI",
        ),
    })):
        validated, vals = await validator.validate_all(profile, enriched)

    symbols = [v.raw.symbol for v in validated]
    assert "BEL" in symbols
    assert "ITC" not in symbols
    assert all(v.theme_match_score >= THEME_MATCH_THRESHOLD for v in vals)
