"""AI Investment Advisor – grounded retrieval, validation, and ranking."""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from app.agents.llm import build_llm
from app.core.config import Settings
from app.llm.caller import call_llm_with_retry
from app.schemas.advisor import (
    ADVISOR_DISCLAIMER,
    AdvisorPortfolioHolding,
    AdvisorRecommendRequest,
    AdvisorRecommendResponse,
    AdvisorRetrievalSummary,
    CandidateValidation,
    CompanyResearchAction,
    InvestorProfile,
    PortfolioMix,
    ProfileFieldDisplay,
    RawCandidate,
    SectorExposureItem,
    StockRecommendation,
    ThemeIntent,
    THEME_MATCH_THRESHOLD,
)
from app.schemas.financial import FinancialSummaryResponse
from app.services.advisor_guardrails import apply_guardrails, ensure_disclaimer
from app.services.advisor_intent_service import AdvisorIntentService, AdvisorIntentType, ClassifiedIntent
from app.services.advisor_profile_display import build_profile_fields
from app.services.advisor_retrieval import AdvisorRetrieval
from app.services.advisor_scoring import (
    overall_match_score,
    score_financial_quality,
    score_risk,
    score_valuation,
)
from app.services.advisor_utils import as_str_list, bare_symbol, extract_json, sanitize_text_list
from app.services.advisor_validation import AdvisorValidator, EnrichedCandidate
from app.services.company_search_service import CompanySearchService
from app.services.financial_data_service import FinancialDataService
from app.services.portfolio_holdings_service import PortfolioHoldingsService
from app.services.symbol_resolver_service import get_symbol_resolver_service
from app.services.rag_service import RagService
from app.services.report_storage_service import ReportStorageService
from app.utils import ttl_cache
from app.utils.logging import get_logger
from app.utils.timing import async_timed_operation

logger = get_logger(__name__)

MAX_RECOMMENDATIONS = 5
SNAPSHOT_TIMEOUT_SECONDS = 8.0

_RANK_SYSTEM = """Rank ONLY from the validated candidates list below.
Return ONLY valid JSON:
{
  "recommendations": [
    {
      "rank": 1,
      "symbol": "must be from validated list",
      "company_name": "...",
      "sector": "...",
      "suggested_allocation_percent": 0-100,
      "why_it_fits": ["why it matches user prompt"],
      "key_risks": ["1-3 risks"],
      "theme_match_reason": "specific theme alignment"
    }
  ],
  "portfolio_mix": {
    "large_cap_percent": 0-100,
    "mid_cap_percent": 0-100,
    "small_cap_percent": 0-100,
    "sector_exposure": [{"sector": "...", "percent": 0-100}],
    "risk_summary": "...",
    "time_horizon_suitability": "..."
  }
}

HARD RULES:
- You may recommend ONLY symbols from validated_candidates. Do not introduce new tickers.
- Return at most 5 recommendations.
- Use research language only. No buy now / place order / guaranteed return.
- If data missing say Not available — do not invent numbers."""


class AdvisorService:
    def __init__(
        self,
        settings: Settings,
        *,
        financial_service: FinancialDataService,
        search_service: CompanySearchService,
        holdings_service: PortfolioHoldingsService | None = None,
        report_storage: ReportStorageService | None = None,
        rag_service: RagService | None = None,
    ) -> None:
        self._settings = settings
        self._financial = financial_service
        self._search = search_service
        self._holdings = holdings_service
        self._storage = report_storage
        self._rag = rag_service
        self._retrieval = AdvisorRetrieval(
            search_service,
            settings.tavily_api_key,
            symbol_resolver=get_symbol_resolver_service(),
        )
        self._validator = AdvisorValidator(settings)
        self._intent_service = AdvisorIntentService(settings)

    async def recommend(self, body: AdvisorRecommendRequest) -> AdvisorRecommendResponse:
        prompt = body.prompt.strip()
        cache_key = self._cache_key(prompt, body.portfolio_context)
        cached = ttl_cache.get("advisor", cache_key)
        if cached is not None:
            return cached

        holdings = await self._resolve_holdings(body.portfolio_context)

        async with async_timed_operation("advisor.classify"):
            classified = await self._intent_service.classify(prompt)

        logger.info("Advisor routed intent=%s", classified.intent)

        if classified.intent == AdvisorIntentType.COMPANY_RESEARCH:
            response = self._company_research_response(classified)
            ttl_cache.set("advisor", cache_key, response)
            return response

        profile = classified.profile
        if classified.themes:
            profile = profile.model_copy(update={"themes": classified.themes})

        broad_market = classified.intent == AdvisorIntentType.MARKET_RECOMMENDATION
        require_themes = classified.intent == AdvisorIntentType.THEME_DISCOVERY

        async with async_timed_operation("advisor.retrieve"):
            raw_candidates, providers_used = await self._retrieval.retrieve_with_fallback(
                profile,
                classified.search_queries,
                classified.theme_keywords,
                broad_market=broad_market,
            )

        retrieval_summary = AdvisorRetrievalSummary(
            raw_candidates_count=len(raw_candidates),
            providers_used=providers_used,
        )

        if not raw_candidates:
            response = self._clarification_response(
                classified,
                retrieval_summary,
                "Could not retrieve candidates from providers. Try a broader prompt or specify NSE sector/theme.",
            )
            ttl_cache.set("advisor", cache_key, response)
            return response

        async with async_timed_operation("advisor.enrich", count=len(raw_candidates)):
            enriched = await self._enrich_candidates(raw_candidates)

        async with async_timed_operation("advisor.validate"):
            if broad_market:
                validated_enriched, validations = await self._validator.validate_market(enriched)
            else:
                validated_enriched, validations = await self._validator.validate_all(profile, enriched)

        validation_map = {v.symbol: v for v in validations}
        retrieval_summary.validated_candidates_count = len(validated_enriched)

        if not validated_enriched and require_themes:
            relaxed_profile = profile.model_copy(update={"themes": profile.themes})
            raw2, prov2 = await self._retrieval.retrieve_with_fallback(
                relaxed_profile,
                classified.search_queries + ["india stock NSE"],
                classified.theme_keywords,
                broad_market=False,
            )
            providers_used = sorted(set(providers_used) | set(prov2))
            retrieval_summary.raw_candidates_count = len(raw2)
            retrieval_summary.providers_used = providers_used
            if raw2:
                enriched2 = await self._enrich_candidates(raw2)
                validated_enriched, validations = await self._validator.validate_all(profile, enriched2)
                validation_map = {v.symbol: v for v in validations}
                retrieval_summary.validated_candidates_count = len(validated_enriched)

        if not validated_enriched:
            response = self._clarification_response(
                classified,
                retrieval_summary,
                (
                    "No reliable matches passed validation for your criteria. "
                    "Try broadening themes, removing exclusions, or ask for top market ideas without a theme filter."
                ),
            )
            ttl_cache.set("advisor", cache_key, response)
            return response

        warnings: list[str] = list(classified.assumptions_used)
        warning: str | None = None
        if len(validated_enriched) < MAX_RECOMMENDATIONS:
            msg = f"Only {len(validated_enriched)} reliable matches found for your criteria."
            warnings.append(msg)
            warning = msg

        if broad_market:
            warnings.insert(
                0,
                "Since no risk, capital, or horizon was provided, this uses a balanced long-term research assumption.",
            )

        async with async_timed_operation("advisor.rank"):
            recommendations, portfolio_mix = await self._rank_validated(
                prompt=prompt,
                profile=profile,
                validated=validated_enriched,
                validation_map=validation_map,
                holdings=holdings,
            )

        allowed = {e.raw.symbol for e in validated_enriched}
        recommendations = apply_guardrails(
            recommendations,
            validation_map,
            allowed,
            require_themes=require_themes,
        )
        recommendations = recommendations[:MAX_RECOMMENDATIONS]
        _normalize_allocations(recommendations)

        logger.info(
            "Advisor final intent=%s raw=%d validated=%d recommendations=%d",
            classified.intent,
            retrieval_summary.raw_candidates_count,
            retrieval_summary.validated_candidates_count,
            len(recommendations),
        )

        response = AdvisorRecommendResponse(
            intent=classified.intent.value,
            investor_profile=profile,
            profile_fields=build_profile_fields(classified),
            recommendations=recommendations,
            portfolio_mix=portfolio_mix,
            disclaimer=ensure_disclaimer(ADVISOR_DISCLAIMER),
            warning=warning,
            assumptions_used=classified.assumptions_used,
            missing_inputs=classified.missing_inputs,
            warnings=warnings,
            retrieval_summary=retrieval_summary,
        )
        ttl_cache.set("advisor", cache_key, response)
        return response

    def _company_research_response(self, classified: ClassifiedIntent) -> AdvisorRecommendResponse:
        sym = classified.company_symbol or "UNKNOWN"
        name = classified.company_name
        return AdvisorRecommendResponse(
            intent=classified.intent.value,
            investor_profile=classified.profile,
            profile_fields=build_profile_fields(classified),
            recommendations=[],
            portfolio_mix=PortfolioMix(),
            disclaimer=ensure_disclaimer(ADVISOR_DISCLAIMER),
            assumptions_used=[],
            missing_inputs=[],
            warnings=[],
            retrieval_summary=AdvisorRetrievalSummary(),
            clarification_message=None,
            company_research_action=CompanyResearchAction(
                symbol=sym,
                company_name=name,
                message=f"Use Stock Overview or Run Full AI Research for {name or sym}.",
            ),
        )

    def _clarification_response(
        self,
        classified: ClassifiedIntent,
        retrieval_summary: AdvisorRetrievalSummary,
        message: str,
    ) -> AdvisorRecommendResponse:
        return AdvisorRecommendResponse(
            intent=classified.intent.value,
            investor_profile=classified.profile,
            profile_fields=build_profile_fields(classified),
            recommendations=[],
            portfolio_mix=PortfolioMix(),
            disclaimer=ensure_disclaimer(ADVISOR_DISCLAIMER),
            assumptions_used=classified.assumptions_used,
            missing_inputs=classified.missing_inputs,
            warnings=[message],
            warning=message,
            retrieval_summary=retrieval_summary,
            clarification_message=message,
        )

    def _cache_key(self, prompt: str, holdings: list[AdvisorPortfolioHolding] | None) -> str:
        holdings_part = ""
        if holdings:
            holdings_part = "|".join(sorted(f"{h.symbol}:{h.current_value}" for h in holdings))
        return hashlib.sha256(f"{prompt.lower()}|{holdings_part}".encode()).hexdigest()[:32]

    async def _resolve_holdings(
        self, explicit: list[AdvisorPortfolioHolding] | None
    ) -> list[AdvisorPortfolioHolding]:
        if explicit:
            return explicit
        if self._holdings is None:
            return []
        try:
            response = await self._holdings.get_holdings()
            if response.auth_required or not response.holdings:
                return []
            return [
                AdvisorPortfolioHolding(
                    symbol=bare_symbol(h.symbol),
                    company_name=h.company_name,
                    sector=h.sector,
                    current_value=h.current_value,
                )
                for h in response.holdings
            ]
        except Exception as exc:
            logger.debug("Kite holdings skipped for advisor: %s", exc)
            return []

    async def _enrich_candidates(self, raw: list[RawCandidate]) -> list[EnrichedCandidate]:
        prior = await self._fetch_prior_reports([c.symbol for c in raw])

        async def _one(candidate: RawCandidate) -> EnrichedCandidate:
            sym = candidate.symbol
            snap: FinancialSummaryResponse | None = None
            try:
                snap = await asyncio.wait_for(
                    self._financial.get_summary(sym),
                    timeout=SNAPSHOT_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                logger.debug("Enrich snapshot failed %s: %s", sym, exc)

            industry = snap.industry if snap else None
            return EnrichedCandidate(
                raw=candidate,
                industry=industry,
                business_summary=None,
                snapshot=snap,
                prior_report_summary=prior.get(sym),
                price_source=snap.price_source if snap else None,
                fundamentals_source=(snap.fundamentals_source or snap.data_source) if snap else None,
            )

        return list(await asyncio.gather(*[_one(c) for c in raw]))

    async def _fetch_prior_reports(self, tickers: list[str]) -> dict[str, str]:
        if not self._storage:
            return {}
        hints: dict[str, str] = {}
        for ticker in tickers:
            try:
                summaries, _ = await self._storage.list_reports(ticker=ticker, limit=1, offset=0)
                if summaries:
                    s = summaries[0]
                    hints[ticker] = (
                        f"Prior report rating={s.rating or 'N/A'} "
                        f"confidence={s.confidence_score or 'N/A'}"
                    )
            except Exception:
                continue
        return hints

    async def _rank_validated(
        self,
        *,
        prompt: str,
        profile: InvestorProfile,
        validated: list[EnrichedCandidate],
        validation_map: dict[str, CandidateValidation],
        holdings: list[AdvisorPortfolioHolding],
    ) -> tuple[list[StockRecommendation], PortfolioMix]:
        ranked_payload = []
        for item in validated:
            val = validation_map[item.raw.symbol]
            snap = item.snapshot
            overall = overall_match_score(val, snap, item.prior_report_summary)
            ranked_payload.append(
                {
                    "symbol": item.raw.symbol,
                    "company_name": item.raw.company_name,
                    "sector": item.raw.sector or (snap.sector if snap else "Not available"),
                    "matched_themes": val.matched_themes,
                    "theme_match_score": val.theme_match_score,
                    "evidence": val.evidence,
                    "overall_match_score": overall,
                    "financial_quality_score": score_financial_quality(snap),
                    "valuation_score": score_valuation(snap),
                    "risk_score": score_risk(snap, val),
                    "data_sources": _data_sources(item),
                    "financial_snapshot": _snapshot_dict(snap),
                }
            )

        ranked_payload.sort(key=lambda x: x["overall_match_score"], reverse=True)

        llm = await asyncio.to_thread(lambda: build_llm(self._settings, skip_probe=True))
        rank_prompt = (
            f"{_RANK_SYSTEM}\n\n"
            f"USER PROMPT:\n{prompt}\n\n"
            f"INVESTOR PROFILE:\n{json.dumps(profile.model_dump(), indent=2)}\n\n"
            f"HOLDINGS:\n{json.dumps([h.model_dump() for h in holdings], indent=2)}\n\n"
            f"VALIDATED_CANDIDATES:\n{json.dumps(ranked_payload, indent=2, default=str)}\n\n"
            "JSON:"
        )
        raw = await asyncio.to_thread(
            call_llm_with_retry,
            llm,
            rank_prompt,
            settings=self._settings,
            label="advisor_llm.rank",
        )
        parsed = extract_json(raw)
        if not isinstance(parsed, dict):
            parsed = {}

        recommendations = _build_recommendations_from_rank(
            parsed, validated, validation_map
        )
        if not recommendations:
            recommendations = _deterministic_rank(validated, validation_map)

        portfolio_mix = _normalize_portfolio_mix(parsed.get("portfolio_mix") or {}, recommendations)
        return recommendations, portfolio_mix


def _data_sources(item: EnrichedCandidate) -> list[str]:
    sources: list[str] = [item.raw.source]
    if item.fundamentals_source:
        sources.append(item.fundamentals_source)
    if item.price_source and item.price_source not in sources:
        sources.append(item.price_source)
    return list(dict.fromkeys(sources))


def _snapshot_dict(snap: FinancialSummaryResponse | None) -> dict[str, Any]:
    if snap is None:
        return {"status": "Not available"}
    return {
        "pe_ratio": snap.pe_ratio,
        "pb_ratio": snap.pb_ratio,
        "roe": snap.roe,
        "debt_to_equity": snap.debt_to_equity,
        "revenue_growth": snap.revenue_growth,
        "profit_margin": snap.profit_margin,
        "dividend_yield": snap.dividend_yield,
        "market_cap": snap.market_cap,
        "current_price": snap.current_price,
    }


def _build_recommendations_from_rank(
    parsed: dict[str, Any],
    validated: list[EnrichedCandidate],
    validation_map: dict[str, CandidateValidation],
) -> list[StockRecommendation]:
    allowed = {e.raw.symbol for e in validated}
    enrich_map = {e.raw.symbol: e for e in validated}
    raw_list = parsed.get("recommendations") or []
    if not isinstance(raw_list, list):
        return []

    out: list[StockRecommendation] = []
    for idx, item in enumerate(raw_list[:MAX_RECOMMENDATIONS], start=1):
        if not isinstance(item, dict):
            continue
        sym = bare_symbol(str(item.get("symbol") or ""))
        if sym not in allowed:
            continue
        val = validation_map[sym]
        enrich = enrich_map[sym]
        snap = enrich.snapshot
        overall = overall_match_score(val, snap, enrich.prior_report_summary)

        out.append(
            StockRecommendation(
                rank=int(item.get("rank") or idx),
                symbol=sym,
                company_name=str(item.get("company_name") or enrich.raw.company_name),
                sector=str(item.get("sector") or enrich.raw.sector or "Not available"),
                match_score=overall,
                overall_match_score=overall,
                theme_match_score=val.theme_match_score,
                matched_themes=val.matched_themes,
                theme_match_reason=str(item.get("theme_match_reason") or val.reason or "Not available"),
                key_evidence=val.evidence,
                financial_quality_score=score_financial_quality(snap),
                valuation_score=score_valuation(snap),
                risk_score=score_risk(snap, val),
                suggested_allocation_percent=float(item.get("suggested_allocation_percent") or 0),
                why_it_fits=sanitize_text_list(item.get("why_it_fits")),
                key_risks=sanitize_text_list(item.get("key_risks")) or ["Market and sector risks apply."],
                data_sources=_data_sources(enrich),
            )
        )
    out.sort(key=lambda r: r.rank)
    return out


def _deterministic_rank(
    validated: list[EnrichedCandidate],
    validation_map: dict[str, CandidateValidation],
) -> list[StockRecommendation]:
    scored: list[tuple[int, EnrichedCandidate]] = []
    for e in validated:
        val = validation_map[e.raw.symbol]
        scored.append((overall_match_score(val, e.snapshot, e.prior_report_summary), e))
    scored.sort(key=lambda x: x[0], reverse=True)

    picks: list[StockRecommendation] = []
    n = min(MAX_RECOMMENDATIONS, len(scored))
    alloc = round(100 / n, 1) if n else 0
    for idx, (overall, enrich) in enumerate(scored[:n], start=1):
        val = validation_map[enrich.raw.symbol]
        picks.append(
            StockRecommendation(
                rank=idx,
                symbol=enrich.raw.symbol,
                company_name=enrich.raw.company_name,
                sector=enrich.raw.sector or "Not available",
                match_score=overall,
                overall_match_score=overall,
                theme_match_score=val.theme_match_score,
                matched_themes=val.matched_themes,
                theme_match_reason=val.reason or "Validated theme alignment.",
                key_evidence=val.evidence,
                financial_quality_score=score_financial_quality(enrich.snapshot),
                valuation_score=score_valuation(enrich.snapshot),
                risk_score=score_risk(enrich.snapshot, val),
                suggested_allocation_percent=alloc,
                why_it_fits=[
                    "May be suitable based on validated theme evidence.",
                    "Worth researching further against your stated goals.",
                ],
                key_risks=["Market volatility and sector-specific risks apply."],
                data_sources=_data_sources(enrich),
            )
        )
    return picks


def _normalize_allocations(recommendations: list[StockRecommendation]) -> None:
    if not recommendations:
        return
    total = sum(r.suggested_allocation_percent for r in recommendations)
    if total <= 0:
        even = round(100 / len(recommendations), 1)
        for r in recommendations:
            r.suggested_allocation_percent = even
        return
    if abs(total - 100) > 5:
        factor = 100 / total
        for r in recommendations:
            r.suggested_allocation_percent = round(r.suggested_allocation_percent * factor, 1)


def _normalize_portfolio_mix(
    raw: dict[str, Any], recommendations: list[StockRecommendation]
) -> PortfolioMix:
    sector_map: dict[str, float] = {}
    for rec in recommendations:
        sector = rec.sector or "Not available"
        sector_map[sector] = sector_map.get(sector, 0) + rec.suggested_allocation_percent

    sector_exposure = [
        SectorExposureItem(sector=k, percent=round(v, 1))
        for k, v in sorted(sector_map.items(), key=lambda x: -x[1])
    ]

    large = float(raw.get("large_cap_percent") or 0)
    mid = float(raw.get("mid_cap_percent") or 0)
    small = float(raw.get("small_cap_percent") or 0)
    if large + mid + small <= 0:
        large, mid, small = 60.0, 30.0, 10.0

    return PortfolioMix(
        large_cap_percent=large,
        mid_cap_percent=mid,
        small_cap_percent=small,
        sector_exposure=sector_exposure,
        risk_summary=str(raw.get("risk_summary") or "Based on validated thematic matches."),
        time_horizon_suitability=str(raw.get("time_horizon_suitability") or "Not available"),
    )


# Backward-compatible exports for tests
_extract_json = extract_json


def _normalize_recommendations(parsed: dict[str, Any], snapshots: dict) -> list[StockRecommendation]:
    """Legacy helper – ranking now uses validated pipeline."""
    return []
