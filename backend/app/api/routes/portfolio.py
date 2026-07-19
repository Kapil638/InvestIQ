"""Portfolio holdings and AI analysis endpoints."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_portfolio_analyze_service, get_portfolio_holdings_service
from app.schemas.portfolio import (
    PortfolioAnalyzeRequest,
    PortfolioAnalyzeResponse,
    PortfolioHoldingsResponse,
)
from app.services.portfolio_analyze_service import PortfolioAnalyzeService
from app.services.portfolio_holdings_service import PortfolioHoldingsService

router = APIRouter(tags=["portfolio"])


@router.get("/kite/holdings", response_model=PortfolioHoldingsResponse)
async def kite_holdings(
    service: PortfolioHoldingsService = Depends(get_portfolio_holdings_service),
) -> PortfolioHoldingsResponse:
    """Zerodha portfolio holdings via Kite MCP (read-only)."""
    return await service.get_holdings()


@router.post("/portfolio/analyze", response_model=PortfolioAnalyzeResponse)
async def analyze_portfolio(
    body: PortfolioAnalyzeRequest,
    service: PortfolioAnalyzeService = Depends(get_portfolio_analyze_service),
) -> PortfolioAnalyzeResponse:
    """
    AI research analysis of portfolio holdings.

    Research-only output – does not place or suggest executing trades.
    """
    return await service.analyze(body)
