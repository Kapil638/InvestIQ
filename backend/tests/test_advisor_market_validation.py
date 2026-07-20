"""Tests for AdvisorValidator.validate_market — the broad market-recommendation
screen. Previously this accepted every candidate unconditionally regardless of
whether any real financial data backed it up, which is how obscure shell/
holding companies (matched by retrieval's plain company-name substring search)
ended up recommended as "large-cap" picks."""

import pytest

from app.schemas.advisor import InvestorProfile, RawCandidate
from app.schemas.financial import FinancialSummaryResponse
from app.services.advisor_validation import AdvisorValidator, EnrichedCandidate


def _candidate(symbol: str, market_cap: float | None, sector: str = "Financial Services") -> EnrichedCandidate:
    snap = (
        FinancialSummaryResponse(ticker=symbol, market_cap=market_cap, sector=sector)
        if market_cap is not None
        else None
    )
    return EnrichedCandidate(
        raw=RawCandidate(
            symbol=symbol, company_name=f"{symbol} Ltd", exchange="NSE", sector=sector, source="test"
        ),
        snapshot=snap,
    )


@pytest.mark.asyncio
async def test_validate_market_rejects_candidates_with_no_snapshot() -> None:
    validator = AdvisorValidator(settings=None)
    candidates = [_candidate("NODATA", market_cap=None)]

    validated, validations = await validator.validate_market(candidates)

    assert validated == []
    assert validations == []


@pytest.mark.asyncio
async def test_validate_market_rejects_small_cap_when_large_cap_requested() -> None:
    validator = AdvisorValidator(settings=None)
    # Rs 500 crore — well within small-cap territory, not large-cap.
    candidates = [_candidate("SMALLCO", market_cap=5_000_000_000.0)]
    profile = InvestorProfile(market_cap_preference="large cap")

    validated, validations = await validator.validate_market(candidates, profile)

    assert validated == []


@pytest.mark.asyncio
async def test_validate_market_accepts_large_cap_when_large_cap_requested() -> None:
    validator = AdvisorValidator(settings=None)
    # Rs 50,000 crore — solidly large-cap.
    candidates = [_candidate("BIGCO", market_cap=500_000_000_000.0)]
    profile = InvestorProfile(market_cap_preference="large cap")

    validated, validations = await validator.validate_market(candidates, profile)

    assert len(validated) == 1
    assert validated[0].raw.symbol == "BIGCO"
    assert validations[0].is_valid is True


@pytest.mark.asyncio
async def test_validate_market_accepts_any_tier_without_explicit_preference() -> None:
    validator = AdvisorValidator(settings=None)
    candidates = [_candidate("SMALLCO", market_cap=5_000_000_000.0)]

    validated, validations = await validator.validate_market(candidates, InvestorProfile())

    assert len(validated) == 1
