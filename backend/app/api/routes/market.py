"""Provider-agnostic market data endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_financial_data_service
from app.schemas.market import MarketHistoryResponse
from app.services.financial_data_service import FinancialDataService
from app.utils.history_timeframe import validate_interval

router = APIRouter(tags=["market"])


@router.get("/market/history/{symbol}", response_model=MarketHistoryResponse)
async def market_history(
    symbol: str,
    interval: str = Query(default="day", description="Candle interval"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    service: FinancialDataService = Depends(get_financial_data_service),
) -> MarketHistoryResponse:
    """
    OHLC history for charting with automatic provider selection.

    Priority: Tapetide MCP -> Kite -> Yahoo Finance.
    """
    try:
        normalized_interval = validate_interval(interval)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = await service.get_price_history_with_source(
        symbol,
        interval=normalized_interval,
        from_date=from_date,
        to_date=to_date,
    )
    return MarketHistoryResponse(
        symbol=symbol.upper(),
        interval=normalized_interval,
        candles=result.candles,
        source=result.source,
    )
