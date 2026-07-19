"""AI Investment Advisor endpoints."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_advisor_service
from app.schemas.advisor import AdvisorRecommendRequest, AdvisorRecommendResponse
from app.services.advisor_service import AdvisorService

router = APIRouter(tags=["advisor"])


@router.post("/advisor/recommend", response_model=AdvisorRecommendResponse)
async def recommend_stocks(
    body: AdvisorRecommendRequest,
    service: AdvisorService = Depends(get_advisor_service),
) -> AdvisorRecommendResponse:
    """
    Goal-based Indian equity suggestions from a natural-language investment prompt.

    Parses investor goals, screens candidates via Tapetide/local/Yahoo, fetches lightweight
    financial snapshots, and ranks top ideas. Does not run full CrewAI reports or place orders.
    """
    return await service.recommend(body)
