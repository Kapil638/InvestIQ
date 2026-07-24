"""Groww Trade API endpoints – read-only status and positions.

No login/callback routes like Kite's: GROWW_API_KEY/GROWW_API_SECRET mint an
access token server-side on demand, with no browser OAuth step. Holdings are
not exposed here separately — they flow through /kite/holdings once merged
by PortfolioHoldingsService, since the user wants one consolidated list
across both brokers rather than two calls to stitch together client-side.
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_groww_service
from app.schemas.groww import GrowwPositionsResponse, GrowwStatusResponse
from app.services.groww_service import GrowwService

router = APIRouter(tags=["groww"])


@router.get("/groww/status", response_model=GrowwStatusResponse)
async def groww_status(
    service: GrowwService = Depends(get_groww_service),
) -> GrowwStatusResponse:
    """Return Groww integration status (always 200 – check `enabled` / `connected`)."""
    return await service.get_status()


@router.get("/groww/positions", response_model=GrowwPositionsResponse)
async def groww_positions(
    service: GrowwService = Depends(get_groww_service),
) -> GrowwPositionsResponse:
    """Open positions via Groww (read-only)."""
    return await service.get_positions()
