"""Financial data endpoints – Indian equities via Yahoo Finance."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_financial_data_service
from app.schemas.financial import FinancialSummaryResponse
from app.services.financial_data_service import FinancialDataService

router = APIRouter(tags=["financials"])


@router.get("/financials/{ticker}", response_model=FinancialSummaryResponse)
async def get_financial_summary(
    ticker: str,
    service: FinancialDataService = Depends(get_financial_data_service),
) -> FinancialSummaryResponse:
    """
    Fetch a compact financial snapshot for an Indian equity ticker.

    Examples:
        GET /api/v1/financials/INFY      -> INFY.NS
        GET /api/v1/financials/RELIANCE  -> RELIANCE.NS
    """
    return await service.get_summary(ticker)
