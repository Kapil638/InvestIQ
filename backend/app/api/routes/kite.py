"""Kite MCP endpoints – read-only market data, OAuth, and portfolio."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.api.dependencies import get_financial_data_service, get_kite_auth_service, get_kite_service
from app.schemas.history import HistoricalCandle
from app.schemas.kite import (
    KitePositionsResponse,
    KiteQuoteResponse,
    KiteStatusResponse,
)
from app.services.financial_data_service import FinancialDataService
from app.services.kite_auth_service import KiteAuthService
from app.services.kite_service import KiteService
from app.utils.exceptions import KiteAuthError
from app.utils.history_timeframe import validate_interval
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["kite"])


@router.get("/kite/status", response_model=KiteStatusResponse)
async def kite_status(
    service: KiteService = Depends(get_kite_service),
) -> KiteStatusResponse:
    """Return Kite integration status (always 200 – check `enabled` / `authenticated`)."""
    return await service.get_status()


@router.get("/kite/login")
async def kite_login(
    auth_service: KiteAuthService = Depends(get_kite_auth_service),
) -> RedirectResponse:
    """Redirect user to Zerodha login (OAuth step 1)."""
    try:
        login_url = auth_service.get_login_url()
    except KiteAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return RedirectResponse(url=login_url, status_code=302)


@router.get("/kite/callback")
async def kite_callback(
    request_token: str | None = Query(default=None),
    status: str | None = Query(default=None),
    auth_service: KiteAuthService = Depends(get_kite_auth_service),
) -> RedirectResponse:
    """OAuth callback – exchange request_token for access_token (server-side only)."""
    try:
        await auth_service.handle_callback(request_token, status)
        return RedirectResponse(
            url=auth_service.get_frontend_redirect_url(success=True),
            status_code=302,
        )
    except KiteAuthError as exc:
        logger.warning("Kite OAuth callback failed: %s", exc)
        return RedirectResponse(
            url=auth_service.get_frontend_redirect_url(success=False),
            status_code=302,
        )


@router.get("/kite/quotes/{symbol}", response_model=KiteQuoteResponse)
async def kite_quote(
    symbol: str,
    service: KiteService = Depends(get_kite_service),
) -> KiteQuoteResponse:
    """Live quote from Kite Connect when authenticated, else Yahoo Finance fallback."""
    return await service.get_quote(symbol)


@router.get("/kite/history/{symbol}", response_model=list[HistoricalCandle])
async def kite_history(
    symbol: str,
    interval: str = Query(default="day", description="Candle interval"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    financial_service: FinancialDataService = Depends(get_financial_data_service),
) -> list[HistoricalCandle]:
    """
    OHLC candle history for charting.

    Uses Kite MCP when enabled, with Yahoo Finance fallback. Returns an empty list
    when no data is available.
    """
    try:
        normalized_interval = validate_interval(interval)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return await financial_service.get_price_history(
        symbol,
        interval=normalized_interval,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/kite/positions", response_model=KitePositionsResponse)
async def kite_positions(
    service: KiteService = Depends(get_kite_service),
) -> KitePositionsResponse:
    """Open positions via Kite Connect when authenticated (read-only)."""
    return await service.get_positions()
