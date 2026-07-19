"""
Health check endpoint.

Why a health route first?
- Confirms the server, routing, and dependency injection work.
- Deployment platforms (Render) use this to verify the service is alive.
- Gives us a minimal test target before adding complex agent logic.
"""

from fastapi import APIRouter, Depends

from app import __version__
from app.api.dependencies import resolve_settings
from app.core.config import Settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(resolve_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        llm_provider=settings.llm_provider,
        llm_model=settings.openrouter_model,
    )
