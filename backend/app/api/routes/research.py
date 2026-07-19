"""
Research endpoints – data collection and full AI pipeline.
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_financial_data_service,
    get_portfolio_holdings_service,
    get_rag_service,
    get_report_storage_service,
    get_research_ask_service,
    get_research_crew_service,
)
from app.api.dependencies import resolve_settings
from app.core.config import Settings
from app.schemas.ask import ResearchAskRequest, ResearchAskResponse
from app.schemas.financial import FinancialResearchResponse
from app.schemas.research import ResearchReportResponse
from app.services.financial_data_service import FinancialDataService
from app.services.portfolio_holdings_service import PortfolioHoldingsService
from app.services.rag_service import RagService
from app.services.report_storage_service import ReportStorageService
from app.services.research_ask_service import ResearchAskService
from app.services.research_crew_service import ResearchCrewService
from app.utils.exceptions import ExternalServiceError
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["research"])


@router.post("/research/{ticker}", response_model=FinancialResearchResponse)
async def collect_financial_research(
    ticker: str,
    service: FinancialDataService = Depends(get_financial_data_service),
) -> FinancialResearchResponse:
    """
    Collect structured financial data for a ticker (Agent 1 data layer only).

    Facts only – no AI analysis or recommendations.
    """
    return await service.collect(ticker)


@router.post("/research/{ticker}/ask", response_model=ResearchAskResponse)
async def ask_research_question(
    ticker: str,
    body: ResearchAskRequest,
    ask_service: ResearchAskService = Depends(get_research_ask_service),
) -> ResearchAskResponse:
    """
    Answer a focused research question for an Indian equity ticker.

    Uses financial snapshot + targeted news context and a single LLM call.
    Does not run the full multi-agent institutional report pipeline.
    """
    return await ask_service.ask(ticker, body.question)


@router.post("/research/{ticker}/report", response_model=ResearchReportResponse)
async def generate_research_report(
    ticker: str,
    crew_service: ResearchCrewService = Depends(get_research_crew_service),
    storage: ReportStorageService = Depends(get_report_storage_service),
    rag: RagService = Depends(get_rag_service),
    holdings_service: PortfolioHoldingsService = Depends(get_portfolio_holdings_service),
    settings: Settings = Depends(resolve_settings),
) -> ResearchReportResponse:
    """
    Run the full InvestIQ multi-agent research pipeline.

    Agents 1 & 2 run in parallel, Agent 3 analyzes, guardrails validate,
    then Agent 4 delivers the final recommendation. Report is auto-saved when storage is enabled.
    Injects institutional memory (prior report + Chroma RAG) and live Kite portfolio
    context when available.
    """
    report = await crew_service.run(
        ticker,
        storage=storage if settings.storage_enabled else None,
        rag=rag if settings.chroma_enabled else None,
        holdings_service=holdings_service,
    )

    if settings.storage_enabled:
        try:
            stored = await storage.save(report)
            return stored.report
        except ExternalServiceError as exc:
            logger.error(
                "Report generated for %s but storage failed; returning unsaved report: %s",
                ticker,
                exc,
            )
            return report

    return report
