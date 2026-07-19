"""Tests for Kite portfolio context injection into research."""

from unittest.mock import AsyncMock

import pytest

from app.schemas.financial import CompanyProfile, FinancialResearchResponse
from app.schemas.news import NewsResearchResponse
from app.schemas.portfolio import PortfolioHolding, PortfolioHoldingsResponse
from app.services.portfolio_research_context import format_portfolio_context_for_research
from app.services.research_context_builder import build_research_context


def test_format_marks_already_owned_with_weight() -> None:
    holdings = [
        PortfolioHolding(
            symbol="INFY",
            company_name="Infosys",
            quantity=10,
            average_price=1400,
            last_price=1500,
            current_value=15000,
            invested_value=14000,
            pnl=1000,
            pnl_percent=7.1,
            sector="IT",
        ),
        PortfolioHolding(
            symbol="RELIANCE",
            company_name="Reliance",
            quantity=5,
            current_value=35000,
            sector="Energy",
        ),
    ]
    text = format_portfolio_context_for_research(holdings, research_ticker="INFY.NS")
    assert text is not None
    assert "ALREADY OWNED: INFY" in text
    assert "weight=" in text
    assert "Top holdings by value:" in text
    assert "Sector exposure" in text


def test_format_marks_not_held() -> None:
    holdings = [
        PortfolioHolding(symbol="TCS", current_value=20000, sector="IT"),
    ]
    text = format_portfolio_context_for_research(holdings, research_ticker="INFY")
    assert text is not None
    assert "NOT CURRENTLY HELD: INFY" in text


def test_portfolio_context_appears_in_agent_prompt_block() -> None:
    fin = FinancialResearchResponse(
        ticker="INFY",
        profile=CompanyProfile(symbol="INFY", company_name="Infosys", price=1500.0),
    )
    news = NewsResearchResponse(ticker="INFY")
    portfolio = format_portfolio_context_for_research(
        [PortfolioHolding(symbol="INFY", quantity=10, current_value=15000)],
        research_ticker="INFY",
    )
    ctx = build_research_context("INFY", fin, news, portfolio_context=portfolio)
    block = ctx.to_agent_prompt_block()
    assert "PORTFOLIO_CONTEXT:" in block
    assert "ALREADY OWNED" in block


@pytest.mark.asyncio
async def test_crew_loads_kite_portfolio_into_context(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings
    from app.services.research_crew_service import ResearchCrewService

    settings = Settings(
        yfinance_enabled=True,
        tavily_api_key="tavily-key",
        openrouter_api_key="openrouter-key",
        llm_provider="openrouter",
        crew_verbose=False,
        cache_enabled=False,
    )
    service = ResearchCrewService(settings=settings)
    captured: dict = {}

    async def fake_collect(symbol, tracer, data_sources):
        return (
            FinancialResearchResponse(
                ticker=symbol,
                profile=CompanyProfile(symbol=symbol, company_name="Infosys", price=1500.0),
            ),
            NewsResearchResponse(ticker=symbol),
            False,
            False,
        )

    def fake_build_context(ticker, fin, news, **kwargs):
        captured.update(kwargs)
        return build_research_context(ticker, fin, news, **kwargs)

    class StopAfterContext(Exception):
        pass

    holdings_service = AsyncMock()
    holdings_service.get_holdings = AsyncMock(
        return_value=PortfolioHoldingsResponse(
            holdings=[
                PortfolioHolding(symbol="INFY", quantity=12, current_value=18000, sector="IT")
            ],
            auth_required=False,
        )
    )

    monkeypatch.setattr(service, "_collect_structured_data_traced", fake_collect)
    monkeypatch.setattr(
        "app.services.research_crew_service.build_research_context",
        fake_build_context,
    )

    import app.services.research_crew_service as crew_mod

    monkeypatch.setattr(
        crew_mod,
        "build_llm",
        lambda *_a, **_k: (_ for _ in ()).throw(StopAfterContext()),
    )

    with pytest.raises(StopAfterContext):
        await service.run("INFY", holdings_service=holdings_service)

    assert captured.get("portfolio_context")
    assert "ALREADY OWNED" in (captured.get("portfolio_context") or "")
