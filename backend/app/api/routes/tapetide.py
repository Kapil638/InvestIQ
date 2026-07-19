"""Tapetide MCP endpoints – read-only Indian exchange market data."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_company_search_service, get_tapetide_service
from app.schemas.history import HistoricalCandle
from app.schemas.tapetide import (
    TapetideHistoryResponse,
    TapetideQuoteResponse,
    TapetideSearchResponse,
    TapetideStatusResponse,
)
from app.services.company_search_service import CompanySearchService
from app.services.tapetide_service import TapetideService
from app.utils.candle_format import to_historical_candles
from app.utils.exceptions import TapetideMcpNotEnabledError, TapetideMcpServiceError
from app.utils.history_timeframe import validate_interval

router = APIRouter(tags=["tapetide"])


@router.get("/tapetide/status", response_model=TapetideStatusResponse)
async def tapetide_status(
    service: TapetideService = Depends(get_tapetide_service),
) -> TapetideStatusResponse:
    """Return Tapetide MCP integration status (always 200 – check `enabled` / `connected`)."""
    return await service.get_status()


@router.get("/tapetide/quotes/{symbol}", response_model=TapetideQuoteResponse)
async def tapetide_quote(
    symbol: str,
    service: TapetideService = Depends(get_tapetide_service),
) -> TapetideQuoteResponse:
    """Live quote from Tapetide MCP when enabled, else Yahoo Finance fallback."""
    try:
        return await service.get_quote(symbol)
    except TapetideMcpNotEnabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TapetideMcpServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/tapetide/history/{symbol}", response_model=list[HistoricalCandle])
async def tapetide_history(
    symbol: str,
    interval: str = Query(default="day", description="Candle interval"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    service: TapetideService = Depends(get_tapetide_service),
) -> list[HistoricalCandle]:
    """OHLC history from Tapetide MCP with Yahoo fallback."""
    try:
        normalized_interval = validate_interval(interval)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        result = await service.get_history(
            symbol,
            interval=normalized_interval,
            from_date=from_date,
            to_date=to_date,
        )
        return to_historical_candles(result.candles)
    except TapetideMcpNotEnabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TapetideMcpServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/tapetide/search", response_model=TapetideSearchResponse)
async def tapetide_search(
    q: str = Query(..., min_length=1, description="Company name or ticker fragment"),
    limit: int = Query(default=12, ge=1, le=15),
    service: CompanySearchService = Depends(get_company_search_service),
) -> TapetideSearchResponse:
    """Debug search endpoint – same provider chain as /search/companies."""
    result = await service.search(q, limit=limit)
    return TapetideSearchResponse(
        results=result.results,
        source=result.source,
        fallback=result.fallback,
    )
