"""
Research crew orchestrator – service-backed data collection + reasoning agents.

Pipeline:
  1. FinancialDataService + NewsResearchService (parallel, deterministic)
  2. ResearchContext builder (immutable shared context)
  3. Analysis CrewAI agent (structured scores + narrative)
  4. Guardrails validation (with optional analysis retry)
  5. Risk CrewAI agent (structured scores + narrative)
  6. Recommendation CrewAI agent (consumes context + scores only)
  7. Deterministic committee scoring + enrichment
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.agents.llm import build_llm
from app.core.config import Settings
from app.guardrails.engine import GuardrailEngine
from app.guardrails.evidence import build_evidence_corpus
from app.guardrails.recommendation_parser import parse_recommendation
from app.guardrails.structured_output_parser import parse_analysis_output, parse_risk_output
from app.models.research_context import ResearchContext
from app.providers.factory import build_financial_data_service
from app.schemas.agent_outputs import AnalysisOutput, RiskOutput
from app.schemas.research import (
    GuardrailResult,
    InvestmentRecommendation,
    ResearchReportResponse,
    StructuredRiskAssessment,
)
from app.services.data_snapshot import compute_data_snapshot_hash
from app.services.investment_committee_service import InvestmentCommitteeService
from app.services.investment_scoring_service import InvestmentScoringService
from app.services.news_research_service import NewsResearchService
from app.services.pipeline_tracer import PipelineTracer
from app.services.portfolio_holdings_service import PortfolioHoldingsService
from app.services.portfolio_research_context import format_portfolio_context_for_research
from app.services.report_storage_service import ReportStorageService
from app.services.rag_service import RagService
from app.services.research_context_builder import build_research_context
from app.services.symbol_resolver_service import get_symbol_resolver_service
from app.services.stage_cache import (
    cache_key_for_analysis,
    cache_key_for_recommendation,
    get_stage,
    hash_payload,
    set_stage,
)
from app.services.tavily_client import TavilyClient
from app.utils import ttl_cache
from app.utils.exceptions import ConfigurationError
from app.utils.logging import get_logger
from app.utils.timing import async_timed_operation

logger = get_logger(__name__)


class ResearchCrewService:
    """Orchestrates the full InvestIQ research pipeline."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._validate_config()

    def _validate_config(self) -> None:
        if self._settings.llm_provider != "openrouter":
            raise ConfigurationError(
                f"Unsupported LLM_PROVIDER '{self._settings.llm_provider}'. "
                "Set LLM_PROVIDER=openrouter in backend/.env"
            )
        if not self._settings.openrouter_api_key:
            raise ConfigurationError("OPENROUTER_API_KEY is required")
        if not self._settings.yfinance_enabled:
            raise ConfigurationError("YFINANCE_ENABLED must be true")
        if not self._settings.tavily_api_key:
            raise ConfigurationError("TAVILY_API_KEY is not configured")

    async def run(
        self,
        ticker: str,
        storage: ReportStorageService | None = None,
        rag: RagService | None = None,
        holdings_service: PortfolioHoldingsService | None = None,
    ) -> ResearchReportResponse:
        symbol = ticker.strip().upper()
        tracer = PipelineTracer()
        data_sources: list[str] = []

        financial_data, news_data, fin_cache, news_cache = await self._collect_structured_data_traced(
            symbol, tracer, data_sources
        )
        data_hash = compute_data_snapshot_hash(symbol, financial_data, news_data)
        logger.info("Data snapshot hash for %s: %s", symbol, data_hash)

        previous_report: ResearchReportResponse | None = None
        if storage:
            previous_stored = await storage.find_latest_by_ticker(symbol)
            if previous_stored is not None:
                previous_report = previous_stored.report
            cached = await storage.find_recent_by_ticker_and_hash(
                symbol, data_hash, within_seconds=120
            )
            if cached and cached.report.pipeline_trace:
                logger.info(
                    "Returning recent report %s for %s (unchanged data hash within 2 min)",
                    cached.id,
                    symbol,
                )
                return cached.report.model_copy(
                    update={"regenerated_from_same_data": True}
                )

        chroma_context = ""
        tracer.start("rag")
        if rag and rag.is_enabled:
            try:
                chroma_context = await rag.get_context_for_ticker(symbol, limit=4)
                tracer.complete(
                    "rag",
                    detail=f"{len(chroma_context)} chars matched" if chroma_context else "no matches",
                )
            except Exception as exc:  # noqa: BLE001 — memory must not block research
                logger.warning("RAG institutional memory unavailable for %s: %s", symbol, exc)
                tracer.fail("rag", error=str(exc))
        else:
            tracer.skip("rag", reason="rag_disabled")

        portfolio_context = await self._load_portfolio_context(symbol, holdings_service)

        context = build_research_context(
            symbol,
            financial_data,
            news_data,
            previous_report=previous_report,
            chroma_context=chroma_context or None,
            portfolio_context=portfolio_context,
        )
        if previous_report or chroma_context or portfolio_context:
            logger.info(
                "Institutional memory for %s: prior_report=%s chroma_chars=%s portfolio=%s",
                symbol,
                bool(previous_report),
                len(chroma_context or ""),
                bool(portfolio_context),
            )

        async with async_timed_operation("research.llm_acquire", ticker=symbol):
            llm = await asyncio.to_thread(build_llm, self._settings)

        model_used = getattr(llm, "model", None)
        if model_used is not None:
            model_used = str(model_used)

        from app.tasks.research_tasks import build_reasoning_agent_pairs

        pairs = build_reasoning_agent_pairs(self._settings, llm)

        engine = GuardrailEngine(self._settings)
        evidence_corpus = build_evidence_corpus(symbol, financial_data, news_data)

        analysis_output, guardrails = await self._run_analysis_stage(
            pairs=pairs,
            context=context,
            ticker=symbol,
            financial_data=financial_data,
            news_data=news_data,
            tracer=tracer,
            engine=engine,
            corpus=evidence_corpus,
        )

        risk_output, risk_guardrails = await self._run_risk_stage(
            pairs=pairs,
            context=context,
            analysis_output=analysis_output,
            data_hash=data_hash,
            tracer=tracer,
            engine=engine,
            corpus=evidence_corpus,
            financial_data=financial_data,
            news_data=news_data,
        )

        structured_risks = StructuredRiskAssessment(
            risks=risk_output.risks,
            source="risk_agent",
            risk_count=len(risk_output.risks),
        )

        recommendation = None
        raw_recommendation = None
        recommendation_guardrails = None
        if guardrails.passed:
            tracer.start("recommendation")
            try:
                (
                    raw_recommendation,
                    recommendation,
                    rec_cache_hit,
                    recommendation_guardrails,
                ) = await self._run_recommendation_stage(
                    pairs=pairs,
                    context=context,
                    analysis_output=analysis_output,
                    risk_output=risk_output,
                    guardrails=guardrails,
                    data_hash=data_hash,
                    engine=engine,
                    corpus=evidence_corpus,
                    financial_data=financial_data,
                    news_data=news_data,
                )
                tracer.complete(
                    "recommendation",
                    cache_hit=rec_cache_hit,
                    detail=_guardrail_trace_detail(recommendation_guardrails),
                )
            except Exception as exc:
                tracer.fail("recommendation", error=str(exc))
                raise
        else:
            tracer.skip("recommendation", reason=guardrails.blocked_reason or "guardrails_failed")
            logger.warning("Guardrails failed for %s: %s", symbol, guardrails.issues)

        tracer.start("committee")
        try:
            draft = ResearchReportResponse(
                ticker=symbol,
                financial_data=financial_data,
                news_data=news_data,
                financial_data_summary=context.financial_summary,
                news_research_summary=context.news_summary,
                analysis=analysis_output.narrative,
                analysis_output=analysis_output,
                structured_risks=structured_risks,
                risk_output=risk_output,
                guardrails=guardrails,
                risk_guardrails=risk_guardrails,
                recommendation_guardrails=recommendation_guardrails,
                recommendation=recommendation,
                raw_recommendation=raw_recommendation,
                data_snapshot_hash=data_hash,
            )

            scoring = InvestmentScoringService().score(
                draft, structured_risks=structured_risks, previous_report=previous_report
            )

            if recommendation:
                recommendation = recommendation.model_copy(
                    update={
                        "rating": scoring.rating,
                        "confidence_score": float(scoring.confidence_score),
                    }
                )

            draft = draft.model_copy(
                update={
                    "recommendation": recommendation,
                    "confidence_score": scoring.confidence_score,
                    "score_breakdown": scoring.score_breakdown,
                    "scoring_version": scoring.scoring_version,
                    "data_snapshot_hash": scoring.data_snapshot_hash,
                    "confidence_change_reason": scoring.confidence_change_reason,
                }
            )

            enriched = InvestmentCommitteeService().enrich(draft)
            tracer.complete("committee", cache_hit=scoring.reused_prior_scoring)
            enriched = enriched.model_copy(
                update={"pipeline_trace": tracer.to_list(), "model_used": model_used}
            )

            _log_pipeline_summary(symbol, enriched.pipeline_trace, fin_cache, news_cache)
            return enriched
        except Exception as exc:
            tracer.fail("committee", error=str(exc))
            raise

    async def _load_portfolio_context(
        self,
        symbol: str,
        holdings_service: PortfolioHoldingsService | None,
    ) -> str | None:
        if holdings_service is None:
            return None
        try:
            response = await holdings_service.get_holdings()
            if response.auth_required or not response.holdings:
                if response.auth_required:
                    logger.info("Portfolio context skipped for %s: Kite auth required", symbol)
                return None
            return format_portfolio_context_for_research(
                response.holdings,
                research_ticker=symbol,
            )
        except Exception as exc:  # noqa: BLE001 — portfolio must not block research
            logger.warning("Portfolio context unavailable for %s: %s", symbol, exc)
            return None

    async def _collect_structured_data_traced(
        self, symbol: str, tracer: PipelineTracer, data_sources: list[str]
    ):
        tavily_client = TavilyClient(api_key=self._settings.tavily_api_key)
        financial_service = build_financial_data_service(self._settings)
        news_service = NewsResearchService(tavily_client=tavily_client)

        resolved = get_symbol_resolver_service().resolve_query(symbol)
        company_name = resolved.company_name if resolved else None

        fin_cache_hit = ttl_cache.get("financial", f"collect:{symbol}") is not None
        news_cache_hit = get_stage("news", symbol) is not None

        tracer.start("financial")
        tracer.start("news")

        async def _fin():
            try:
                result = await financial_service.collect(symbol)
                tracer.complete("financial", cache_hit=fin_cache_hit)
                if result.data_sources:
                    data_sources.extend(result.data_sources)
                return result
            except Exception as exc:
                tracer.fail("financial", error=str(exc))
                raise

        async def _news():
            try:
                cached = get_stage("news", symbol)
                if cached is not None:
                    tracer.complete("news", cache_hit=True)
                    return cached
                result = await news_service.collect(symbol, company_name=company_name)
                set_stage("news", symbol, result)
                tracer.complete("news", cache_hit=news_cache_hit)
                data_sources.append("tavily")
                return result
            except Exception as exc:
                tracer.fail("news", error=str(exc))
                raise

        try:
            financial_data, news_data = await asyncio.gather(_fin(), _news())
            return financial_data, news_data, fin_cache_hit, news_cache_hit
        finally:
            await tavily_client.close()

    async def _run_analysis_stage(
        self,
        pairs: dict,
        context: ResearchContext,
        ticker: str,
        financial_data,
        news_data,
        tracer: PipelineTracer,
        engine: GuardrailEngine,
        corpus,
    ):
        guardrail_feedback = ""
        retry_count = 0
        max_retries = self._settings.guardrail_max_analysis_retries
        data_hash = context.data_snapshot_hash

        cached = get_stage("analysis", data_hash)
        tracer.start("analysis")
        if cached is not None:
            analysis_output = AnalysisOutput.model_validate(cached)
            tracer.complete("analysis", cache_hit=True)
            logger.info("Analysis cache hit for %s hash=%s", ticker, data_hash)
        else:
            try:
                raw = await self._run_analysis_crew(
                    pairs,
                    {
                        "ticker": ticker,
                        "research_context": context.to_agent_prompt_block(),
                        "guardrail_feedback": guardrail_feedback,
                    },
                )
                analysis_output = parse_analysis_output(raw)
                set_stage("analysis", data_hash, analysis_output.model_dump())
                tracer.complete("analysis")
                logger.info("Analysis completed for %s (%.0fms overall score)", ticker, analysis_output.scores.overall)
            except Exception as exc:
                tracer.fail("analysis", error=str(exc))
                raise

        tracer.start("guardrails")
        guardrails = engine.validate(
            ticker, financial_data, news_data, analysis_output.narrative, corpus=corpus
        )

        while not guardrails.passed and retry_count < max_retries:
            if not GuardrailEngine.is_retryable(guardrails):
                break
            retry_count += 1
            logger.info(
                "Guardrails failed for %s – retrying analysis (%d/%d)",
                ticker,
                retry_count,
                max_retries,
            )
            guardrail_feedback = GuardrailEngine.format_feedback(guardrails.issues)
            raw = await self._run_analysis_crew(
                pairs,
                {
                    "ticker": ticker,
                    "research_context": context.to_agent_prompt_block(),
                    "guardrail_feedback": guardrail_feedback,
                },
            )
            analysis_output = parse_analysis_output(raw)
            set_stage("analysis", data_hash, analysis_output.model_dump())
            guardrails = engine.validate(
                ticker, financial_data, news_data, analysis_output.narrative, corpus=corpus
            )

        guardrails.retry_count = retry_count
        tracer.complete("guardrails", detail=_guardrail_trace_detail(guardrails))
        return analysis_output, guardrails

    async def _run_risk_stage(
        self,
        pairs: dict,
        context: ResearchContext,
        analysis_output: AnalysisOutput,
        data_hash: str,
        tracer: PipelineTracer,
        engine: GuardrailEngine,
        corpus,
        financial_data,
        news_data,
    ) -> tuple[RiskOutput, GuardrailResult]:
        analysis_hash = hash_payload(analysis_output.model_dump())
        cached = get_stage("risk", data_hash, analysis_hash)

        tracer.start("risk")
        if cached is not None:
            risk_output = RiskOutput.model_validate(cached)
            risk_guardrails = engine.validate(
                context.ticker,
                financial_data,
                news_data,
                risk_output.narrative,
                corpus=corpus,
            )
            if not risk_guardrails.passed:
                logger.warning(
                    "Risk guardrails failed for %s: %s",
                    context.ticker,
                    [issue.code for issue in risk_guardrails.issues],
                )
            tracer.complete(
                "risk",
                cache_hit=True,
                detail=_guardrail_trace_detail(risk_guardrails),
            )
            logger.info("Risk cache hit for %s", context.ticker)
            return risk_output, risk_guardrails

        try:
            raw = await self._run_risk_crew(
                pairs,
                {
                    "ticker": context.ticker,
                    "research_context": context.to_agent_prompt_block(compact=True),
                    "analysis": analysis_output.narrative,
                    "analysis_scores": analysis_output.scores.model_dump_json(),
                },
            )
            risk_output = parse_risk_output(raw)
            risk_guardrails = engine.validate(
                context.ticker,
                financial_data,
                news_data,
                risk_output.narrative,
                corpus=corpus,
            )
            if not risk_guardrails.passed:
                logger.warning(
                    "Risk guardrails failed for %s: %s",
                    context.ticker,
                    [issue.code for issue in risk_guardrails.issues],
                )
            set_stage("risk", data_hash, risk_output.model_dump(), analysis_hash)
            tracer.complete("risk", detail=_guardrail_trace_detail(risk_guardrails))
            logger.info(
                "Risk completed for %s overall_risk=%s",
                context.ticker,
                risk_output.scores.overall_risk,
            )
            return risk_output, risk_guardrails
        except Exception as exc:
            tracer.fail("risk", error=str(exc))
            raise

    async def _run_recommendation_stage(
        self,
        pairs: dict,
        context: ResearchContext,
        analysis_output: AnalysisOutput,
        risk_output: RiskOutput,
        guardrails,
        data_hash: str,
        engine: GuardrailEngine,
        corpus,
        financial_data,
        news_data,
    ) -> tuple[str, InvestmentRecommendation, bool, GuardrailResult]:
        analysis_hash = hash_payload(analysis_output.model_dump())
        risk_hash = hash_payload(risk_output.model_dump())
        cached = get_stage("recommendation", data_hash, analysis_hash, risk_hash)
        if cached is not None:
            raw = cached["raw"]
            rec = InvestmentRecommendation.model_validate(cached["recommendation"])
            recommendation_guardrails = engine.validate(
                context.ticker,
                financial_data,
                news_data,
                rec.reasoning,
                corpus=corpus,
            )
            if not recommendation_guardrails.passed:
                logger.warning(
                    "Recommendation guardrails failed for %s: %s",
                    context.ticker,
                    [issue.code for issue in recommendation_guardrails.issues],
                )
            return raw, rec, True, recommendation_guardrails

        guardrails_status = json.dumps(
            {"passed": guardrails.passed, "issues": [i.model_dump() for i in guardrails.issues]}
        )
        raw = await self._run_recommendation_crew(
            pairs,
            {
                "ticker": context.ticker,
                "research_context": context.to_agent_prompt_block(compact=True),
                "analysis": analysis_output.narrative,
                "analysis_scores": analysis_output.scores.model_dump_json(),
                "risk_narrative": risk_output.narrative,
                "risk_scores": risk_output.scores.model_dump_json(),
                "guardrails_status": guardrails_status,
            },
        )
        parsed = parse_recommendation(raw)
        recommendation_guardrails = engine.validate(
            context.ticker,
            financial_data,
            news_data,
            parsed.reasoning,
            corpus=corpus,
        )
        if not recommendation_guardrails.passed:
            logger.warning(
                "Recommendation guardrails failed for %s: %s",
                context.ticker,
                [issue.code for issue in recommendation_guardrails.issues],
            )
        merged_risks = list(risk_output.risks)
        for risk in parsed.risks:
            if risk not in merged_risks:
                merged_risks.append(risk)
        recommendation = parsed.model_copy(
            update={
                "risks": merged_risks[:8],
                "llm_suggested_confidence": parsed.confidence_score,
                "confidence_score": 0,
            }
        )
        set_stage(
            "recommendation",
            data_hash,
            {"raw": raw, "recommendation": recommendation.model_dump()},
            analysis_hash,
            risk_hash,
        )
        return raw, recommendation, False, recommendation_guardrails

    async def _run_analysis_crew(self, pairs: dict, inputs: dict[str, Any]) -> str:
        return await self._run_single_agent_crew(pairs["analysis"], inputs)

    async def _run_risk_crew(self, pairs: dict, inputs: dict[str, Any]) -> str:
        return await self._run_single_agent_crew(pairs["risk"], inputs)

    async def _run_recommendation_crew(self, pairs: dict, inputs: dict[str, Any]) -> str:
        return await self._run_single_agent_crew(pairs["recommendation"], inputs)

    async def _run_single_agent_crew(self, pair: tuple, inputs: dict[str, Any]) -> str:
        from crewai import Crew, Process

        agent, task = pair
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=self._settings.crew_verbose,
        )
        return await self._kickoff_crew(crew, inputs)

    async def _kickoff_crew(self, crew: Any, inputs: dict[str, Any]) -> str:
        if hasattr(crew, "akickoff"):
            result = await crew.akickoff(inputs=inputs)
        else:
            result = await asyncio.to_thread(crew.kickoff, inputs)
        return result.raw if hasattr(result, "raw") else str(result)


def _guardrail_trace_detail(result: GuardrailResult | None) -> str | None:
    if result is None or result.passed:
        return None
    codes = ", ".join(issue.code for issue in result.issues)
    return f"guardrails_failed: {codes}"


def _log_pipeline_summary(
    ticker: str,
    trace: list,
    fin_cache: bool,
    news_cache: bool,
) -> None:
    for entry in trace:
        if entry.status != "completed":
            continue
        duration_s = (entry.duration_ms or 0) / 1000
        cache = " (cache hit)" if entry.cache_hit else ""
        logger.info("%s stage %s completed (%.1fs)%s", ticker, entry.stage, duration_s, cache)
    if fin_cache:
        logger.info("%s financial service cache hit", ticker)
    if news_cache:
        logger.info("%s news service cache hit", ticker)
