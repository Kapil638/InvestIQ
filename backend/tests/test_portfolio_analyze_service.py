"""Tests for the enriched portfolio analysis - real fundamentals + deterministic
concentration metrics, not just an LLM guessing from a bare holdings list."""

import json
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.schemas.financial import FinancialSummaryResponse
from app.schemas.portfolio import PortfolioAnalyzeHoldingInput, PortfolioAnalyzeRequest
from app.services.portfolio_analyze_service import (
    PortfolioAnalyzeService,
    _as_percent,
    _compute_concentration_metrics,
    _EnrichedHolding,
    _resolve_sector,
)


def _holding(**overrides) -> PortfolioAnalyzeHoldingInput:
    defaults = dict(symbol="TEST", quantity=10, average_price=100, last_price=110, current_value=1100)
    defaults.update(overrides)
    return PortfolioAnalyzeHoldingInput(**defaults)


def _summary(**overrides) -> FinancialSummaryResponse:
    defaults = dict(ticker="TEST", sector="Technology")
    defaults.update(overrides)
    return FinancialSummaryResponse(**defaults)


def test_resolve_sector_prefers_fetched_summary_over_kite() -> None:
    e = _EnrichedHolding(
        holding=_holding(sector="Kite Sector"),
        summary=_summary(sector="Real Sector"),
    )
    assert _resolve_sector(e) == "Real Sector"


def test_resolve_sector_falls_back_to_kite_when_no_summary() -> None:
    e = _EnrichedHolding(holding=_holding(sector="Kite Sector"), summary=None)
    assert _resolve_sector(e) == "Kite Sector"


def test_resolve_sector_falls_back_to_unknown() -> None:
    e = _EnrichedHolding(holding=_holding(sector=None), summary=None)
    assert _resolve_sector(e) == "Unknown"


def test_sector_exposure_computed_from_real_fundamentals() -> None:
    enriched = [
        _EnrichedHolding(
            holding=_holding(symbol="TCS", current_value=6000),
            summary=_summary(ticker="TCS", sector="IT"),
        ),
        _EnrichedHolding(
            holding=_holding(symbol="INFY", current_value=4000),
            summary=_summary(ticker="INFY", sector="IT"),
        ),
    ]
    metrics = _compute_concentration_metrics(enriched)

    assert len(metrics.sector_exposure) == 1
    assert metrics.sector_exposure[0].sector == "IT"
    assert metrics.sector_exposure[0].allocation_percent == 100.0
    assert set(metrics.sector_exposure[0].holdings) == {"TCS", "INFY"}


def test_flags_single_sector_concentration_over_threshold() -> None:
    enriched = [
        _EnrichedHolding(
            holding=_holding(symbol="RELIANCE", current_value=9000),
            summary=_summary(ticker="RELIANCE", sector="Energy"),
        ),
        _EnrichedHolding(
            holding=_holding(symbol="INFY", current_value=1000),
            summary=_summary(ticker="INFY", sector="IT"),
        ),
    ]
    metrics = _compute_concentration_metrics(enriched)

    assert any("Energy" in f and "90.0%" in f for f in metrics.flags)


def test_flags_single_stock_concentration_over_threshold() -> None:
    enriched = [
        _EnrichedHolding(
            holding=_holding(symbol="RELIANCE", current_value=3000),
            summary=_summary(ticker="RELIANCE", sector="Energy"),
        ),
        _EnrichedHolding(
            holding=_holding(symbol="A", current_value=1000),
            summary=_summary(ticker="A", sector="IT"),
        ),
        _EnrichedHolding(
            holding=_holding(symbol="B", current_value=1000),
            summary=_summary(ticker="B", sector="FMCG"),
        ),
    ]
    metrics = _compute_concentration_metrics(enriched)

    assert any("RELIANCE alone is 60.0%" in f for f in metrics.flags)


def test_flags_high_pe_combined_with_loss() -> None:
    enriched = [
        _EnrichedHolding(
            holding=_holding(symbol="EXPENSIVE", current_value=1000, pnl_percent=-15.0),
            summary=_summary(ticker="EXPENSIVE", sector="IT", pe_ratio=80.0),
        ),
    ]
    metrics = _compute_concentration_metrics(enriched)

    assert any("EXPENSIVE" in f and "P/E of 80.0x" in f for f in metrics.flags)


def test_does_not_flag_high_pe_without_loss() -> None:
    """High P/E alone isn't a red flag - only combined with an actual loss.
    EXPENSIVE is kept under both the single-stock (20%) and single-sector
    (40%) concentration thresholds so no unrelated flag also happens to
    name it, isolating the P/E-specific behavior being tested."""
    enriched = [
        _EnrichedHolding(
            holding=_holding(symbol="EXPENSIVE", current_value=500, pnl_percent=5.0),
            summary=_summary(ticker="EXPENSIVE", sector="IT", pe_ratio=80.0),
        ),
        _EnrichedHolding(
            holding=_holding(symbol="B", current_value=1500),
            summary=_summary(ticker="B", sector="FMCG"),
        ),
        _EnrichedHolding(
            holding=_holding(symbol="C", current_value=1500),
            summary=_summary(ticker="C", sector="Energy"),
        ),
        _EnrichedHolding(
            holding=_holding(symbol="D", current_value=1500),
            summary=_summary(ticker="D", sector="Healthcare"),
        ),
    ]
    metrics = _compute_concentration_metrics(enriched)

    assert not any("EXPENSIVE" in f for f in metrics.flags)


def test_flags_high_debt_to_equity() -> None:
    enriched = [
        _EnrichedHolding(
            holding=_holding(symbol="LEVERAGED", current_value=1000),
            summary=_summary(ticker="LEVERAGED", sector="Telecom", debt_to_equity=200.0),
        ),
    ]
    metrics = _compute_concentration_metrics(enriched)

    assert any("LEVERAGED" in f and "200.0%" in f for f in metrics.flags)


def test_flags_low_roe() -> None:
    enriched = [
        _EnrichedHolding(
            holding=_holding(symbol="WEAK", current_value=1000),
            summary=_summary(ticker="WEAK", sector="FMCG", roe=2.0),
        ),
    ]
    metrics = _compute_concentration_metrics(enriched)

    assert any("WEAK" in f and "2.0%" in f for f in metrics.flags)


def test_as_percent_converts_yahoo_fraction() -> None:
    assert _as_percent(0.42) == pytest.approx(42.0)


def test_as_percent_leaves_already_scaled_value_unchanged() -> None:
    assert _as_percent(50.0) == 50.0


def test_as_percent_handles_none() -> None:
    assert _as_percent(None) is None


def test_does_not_flag_genuinely_strong_roe_expressed_as_fraction() -> None:
    """Regression test: observed live against real Yahoo data - TCS's real
    ROE (a strong ~42%, arriving from Yahoo as the raw fraction 0.42) was
    being compared directly against the percentage threshold without
    converting fraction -> percent first, so 0.42 < 5.0 was true and a
    genuinely excellent ROE got flagged as "below typical benchmarks"."""
    enriched = [
        _EnrichedHolding(
            holding=_holding(symbol="TCS", current_value=1000),
            summary=_summary(ticker="TCS", sector="IT", roe=0.42),
        ),
    ]
    metrics = _compute_concentration_metrics(enriched)

    assert not any("TCS" in f and "return on equity" in f for f in metrics.flags)


def test_flags_low_roe_expressed_as_fraction() -> None:
    """A genuinely weak ROE (2%), arriving from Yahoo as the raw fraction
    0.02, should still be correctly flagged once converted to percent."""
    enriched = [
        _EnrichedHolding(
            holding=_holding(symbol="WEAK", current_value=1000),
            summary=_summary(ticker="WEAK", sector="FMCG", roe=0.02),
        ),
    ]
    metrics = _compute_concentration_metrics(enriched)

    assert any("WEAK" in f and "2.0%" in f for f in metrics.flags)


def test_missing_fundamentals_do_not_crash_metrics() -> None:
    enriched = [_EnrichedHolding(holding=_holding(symbol="NODATA", current_value=1000), summary=None)]
    metrics = _compute_concentration_metrics(enriched)
    assert metrics.sector_exposure[0].sector == "Unknown"


@pytest.mark.asyncio
async def test_analyze_overrides_llm_sector_exposure_with_computed_values() -> None:
    """The LLM's own sector_exposure arithmetic must never be trusted -
    analyze() always replaces it with the deterministic computation."""
    settings = Settings(app_env="test", debug=True, openrouter_api_key="test-key")
    financial_service = AsyncMock()
    financial_service.get_summary.return_value = _summary(sector="IT", pe_ratio=25.0)

    service = PortfolioAnalyzeService(settings=settings, financial_data_service=financial_service)

    llm_json = json.dumps(
        {
            "summary": "Test",
            "concentration_risk": "Test",
            "sector_exposure": [{"sector": "Wrong Sector", "allocation_percent": 1, "holdings": []}],
            "rebalance_suggestions": ["An additional LLM suggestion"],
            "three_year_view": "Test",
        }
    )

    import app.services.portfolio_analyze_service as mod

    original_build_llm = mod.build_llm
    mod.build_llm = lambda _settings: type("L", (), {"call": staticmethod(lambda _p: llm_json)})()
    try:
        request = PortfolioAnalyzeRequest(holdings=[_holding(symbol="TCS", current_value=1000)])
        response = await service.analyze(request)
    finally:
        mod.build_llm = original_build_llm

    assert response.sector_exposure[0].sector == "IT"  # not "Wrong Sector"
    assert "An additional LLM suggestion" in response.rebalance_suggestions
