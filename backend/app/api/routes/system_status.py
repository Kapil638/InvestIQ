"""Aggregated status endpoints for the in-app system status dashboard.

Deliberately separate from health.py's /health - that route is Render's own
uptime probe and must stay minimal and always-fast; a DB hiccup here should
never cause Render to think the whole service is down and restart it.
"""

import time

from fastapi import APIRouter, Depends

from app.api.dependencies import get_report_storage_service
from app.schemas.system_status import DatabaseStatusResponse
from app.services.report_storage_service import ReportStorageService
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["system-status"])


@router.get("/status/database", response_model=DatabaseStatusResponse)
async def database_status(
    storage: ReportStorageService = Depends(get_report_storage_service),
) -> DatabaseStatusResponse:
    """Real Supabase connectivity check (a trivial list_reports call), not
    just a "configured" flag - proves the DB is actually reachable right now."""
    start = time.monotonic()
    try:
        await storage.list_reports(limit=1, offset=0)
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        return DatabaseStatusResponse(connected=True, message="Supabase reachable.", latency_ms=latency_ms)
    except Exception as exc:
        logger.warning("Database status check failed: %s", exc)
        return DatabaseStatusResponse(connected=False, message=str(exc))
