from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings
from app.guardrails.checks.hallucination import check_hallucinations
from app.guardrails.checks.staleness import check_staleness
from app.guardrails.engine import GuardrailEngine
from app.guardrails.evidence import build_evidence_corpus
from app.guardrails.recommendation_parser import parse_recommendation
from app.schemas.financial import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    FinancialResearchResponse,
    IncomeStatement,
)
from app.schemas.news import NewsArticle, NewsResearchResponse
from app.schemas.research import RecommendationRating


def _settings() -> Settings:
    return Settings(
        guardrail_collection_max_age_hours=24,
        guardrail_statement_max_age_months=18,
        guardrail_news_max_age_days=30,
        guardrail_block_on_warnings=False,
    )


def _financial_data(
    *,
    collected_at: datetime | None = None,
    statement_date: str = "2026-03-28",
    revenues: list[float] | None = None,
) -> FinancialResearchResponse:
    revenues = revenues or [900000, 1000000]
    return FinancialResearchResponse(
        ticker="AAPL",
        collected_at=collected_at or datetime.now(UTC),
        profile=CompanyProfile(
            symbol="AAPL",
            company_name="Apple Inc.",
            sector="Technology",
            market_cap=3_000_000_000_000,
        ),
        income_statements=[
            IncomeStatement(date=statement_date, revenue=rev) for rev in revenues[-2:]
        ],
        balance_sheets=[
            BalanceSheet(date=statement_date, total_assets=500000, total_equity=300000),
        ],
    )


def _news_data(
    *,
    collected_at: datetime | None = None,
    published_date: str | None = "2026-06-01",
) -> NewsResearchResponse:
    return NewsResearchResponse(
        ticker="AAPL",
        collected_at=collected_at or datetime.now(UTC),
        latest_news=[
            NewsArticle(
                title="Apple beats earnings",
                url="https://example.com",
                published_date=published_date,
            )
        ],
    )


def _valid_analysis() -> str:
    return (
        "AAPL shows strong fundamentals with solid revenue growth near $1,000,000, expanding "
        "services margins, manageable debt, and positive cash flow. Valuation remains reasonable "
        "given growth prospects. Key risks include competition and regulatory pressure."
    )


def test_guardrails_pass_with_valid_inputs() -> None:
    engine = GuardrailEngine(_settings())
    result = engine.validate(
        ticker="AAPL",
        financial_data=_financial_data(),
        news_data=_news_data(),
        analysis=_valid_analysis(),
    )
    assert result.passed is True
    assert result.blocked_reason is None


def test_guardrails_fail_without_financial_data() -> None:
    engine = GuardrailEngine(_settings())
    result = engine.validate(
        ticker="AAPL",
        financial_data=None,
        news_data=_news_data(),
        analysis=_valid_analysis(),
    )
    assert result.passed is False
    assert any(issue.code == "missing_financial_data" for issue in result.issues)


def test_guardrails_fail_with_short_analysis() -> None:
    engine = GuardrailEngine(_settings())
    result = engine.validate(
        ticker="AAPL",
        financial_data=_financial_data(),
        news_data=_news_data(),
        analysis="Too short",
    )
    assert result.passed is False
    assert any(issue.code == "insufficient_analysis" for issue in result.issues)


def test_guardrails_detect_unsupported_numeric_claims() -> None:
    engine = GuardrailEngine(_settings())
    analysis = (
        "AAPL is exceptional with revenue of $500 billion and a 99% net margin. "
        "Growth and valuation look attractive with manageable debt and solid cash flow."
    )
    result = engine.validate(
        ticker="AAPL",
        financial_data=_financial_data(),
        news_data=_news_data(),
        analysis=analysis,
    )
    assert result.passed is False
    assert any(issue.code == "unsupported_numeric_claims" for issue in result.issues)


def test_guardrails_detect_premature_recommendation() -> None:
    engine = GuardrailEngine(_settings())
    analysis = (
        "AAPL fundamentals are strong with revenue growth and improving margins. "
        "We recommend buying the stock now. Risks include competition and regulation."
    )
    result = engine.validate(
        ticker="AAPL",
        financial_data=_financial_data(),
        news_data=_news_data(),
        analysis=analysis,
    )
    assert result.passed is False
    assert any(issue.code == "premature_recommendation" for issue in result.issues)


def test_guardrails_detect_stale_financial_statements() -> None:
    engine = GuardrailEngine(_settings())
    result = engine.validate(
        ticker="AAPL",
        financial_data=_financial_data(statement_date="2020-01-01"),
        news_data=_news_data(),
        analysis=_valid_analysis(),
    )
    assert result.passed is False
    assert any(issue.code == "stale_financial_statements" for issue in result.issues)


def test_guardrails_detect_outdated_news() -> None:
    engine = GuardrailEngine(_settings())
    result = engine.validate(
        ticker="AAPL",
        financial_data=_financial_data(),
        news_data=_news_data(published_date="2020-01-01"),
        analysis=_valid_analysis(),
    )
    assert result.passed is True  # outdated news is a warning, not error
    assert any(issue.code == "outdated_news" for issue in result.issues)


def test_guardrails_detect_revenue_contradiction() -> None:
    engine = GuardrailEngine(_settings())
    financial = FinancialResearchResponse(
        ticker="AAPL",
        collected_at=datetime.now(UTC),
        profile=CompanyProfile(symbol="AAPL", company_name="Apple Inc."),
        income_statements=[
            IncomeStatement(date="2026-01-01", revenue=900000),
            IncomeStatement(date="2026-03-28", revenue=1000000),
        ],
        balance_sheets=[
            BalanceSheet(date="2026-03-28", total_assets=500000, total_equity=300000),
        ],
    )
    analysis = (
        "AAPL faces declining revenue and shrinking margins across its core hardware segment. "
        "Debt levels and cash flow require monitoring. Valuation and competitive risks remain."
    )
    result = engine.validate(
        ticker="AAPL",
        financial_data=financial,
        news_data=_news_data(),
        analysis=analysis,
    )
    assert result.passed is False
    assert any(issue.code == "contradictory_revenue_claim" for issue in result.issues)


def test_retryable_guardrail_failures() -> None:
    engine = GuardrailEngine(_settings())
    result = engine.validate(
        ticker="AAPL",
        financial_data=_financial_data(),
        news_data=_news_data(),
        analysis="Too short",
    )
    assert result.passed is False
    assert any(issue.code == "insufficient_analysis" for issue in result.issues)
    assert GuardrailEngine.is_retryable(result) is True


def test_non_retryable_guardrail_failures() -> None:
    engine = GuardrailEngine(_settings())
    result = engine.validate(
        ticker="AAPL",
        financial_data=None,
        news_data=_news_data(),
        analysis=_valid_analysis(),
    )
    assert GuardrailEngine.is_retryable(result) is False


def test_hallucination_checker_flags_unknown_money() -> None:
    corpus = build_evidence_corpus("AAPL", _financial_data(), _news_data())
    issues = check_hallucinations(
        "Revenue reached $999 billion with exceptional growth and margin expansion.",
        corpus,
    )
    assert any(issue.code == "unsupported_numeric_claims" for issue in issues)


def test_evidence_corpus_includes_cash_flow_statement_numbers() -> None:
    """Regression test: build_evidence_corpus previously never looked at
    cash_flow_statements at all, so any analysis correctly citing operating
    cash flow, free cash flow, or capex was always flagged as hallucinated
    (observed in production for MSTCLTD: real FY26 operating cash flow of
    -277,942,000 was blocked as an "unsupported numeric claim")."""
    financial = _financial_data().model_copy(
        update={
            "cash_flow_statements": [
                CashFlowStatement(
                    date="2026-03-31",
                    operating_cash_flow=-277_942_000.0,
                    free_cash_flow=-500_498_000.0,
                )
            ]
        }
    )
    corpus = build_evidence_corpus("AAPL", financial, None)
    assert -277_942_000.0 in corpus.numbers
    assert -500_498_000.0 in corpus.numbers


def test_hallucination_checker_matches_negative_real_values() -> None:
    """Regression test: the money regex never captures a leading minus sign,
    so a real negative figure (e.g. a cash flow loss) must be matched by
    magnitude, not signed ratio - previously `value / known` on a negative
    `known` produced a negative ratio that always failed the 0.85-1.15 check."""
    financial = _financial_data().model_copy(
        update={
            "cash_flow_statements": [
                CashFlowStatement(date="2026-03-31", operating_cash_flow=-277_942_000.0)
            ]
        }
    )
    corpus = build_evidence_corpus("AAPL", financial, None)
    issues = check_hallucinations(
        "AAPL reported operating cash flow of 277.94 million for the year, a notable decline.",
        corpus,
    )
    assert not any(issue.code == "unsupported_numeric_claims" for issue in issues)


def test_staleness_flags_old_collection() -> None:
    corpus = build_evidence_corpus(
        "AAPL",
        _financial_data(collected_at=datetime.now(UTC) - timedelta(hours=48)),
        None,
    )
    issues = check_staleness(
        _financial_data(collected_at=datetime.now(UTC) - timedelta(hours=48)),
        None,
        corpus,
        collection_max_age_hours=24,
    )
    assert any(issue.code == "stale_financial_data" for issue in issues)


def test_parse_recommendation_extracts_rating_and_confidence() -> None:
    raw = """
    Rating: Buy
    Confidence Score: 78
    Reasoning: Strong revenue growth and expanding margins support a bullish view.
    Key Risks:
    - Regulatory pressure in EU
    - Supply chain concentration
    Target Price Range: $200-$220
    Investment Horizon: Medium term (12-18 months)
    Portfolio Allocation: Core holding at 3-5%
    """
    rec = parse_recommendation(raw)
    assert rec.rating == RecommendationRating.BUY
    assert rec.confidence_score == 0.0
    assert rec.llm_suggested_confidence == 78.0
    assert len(rec.risks) >= 2
    assert rec.target_price_range is not None
