"""Company search endpoints."""

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_company_search_service
from app.schemas.company_search import CompanySearchResponse
from app.services.company_search_service import CompanySearchService

router = APIRouter(tags=["search"])


@router.get("/search/companies", response_model=CompanySearchResponse)
async def search_companies(
    q: str = Query(..., min_length=1, description="Company name or ticker fragment"),
    limit: int = Query(default=12, ge=1, le=15),
    service: CompanySearchService = Depends(get_company_search_service),
) -> CompanySearchResponse:
    """Search Tapetide MCP primary, local master and Yahoo/static fallback."""
    return await service.search(q, limit=limit)
