"""Intent classification and explicit-only profile extraction for Advisor."""

from __future__ import annotations

import asyncio
import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.agents.llm import build_llm
from app.core.config import Settings
from app.llm.caller import call_llm_with_retry
from app.schemas.advisor import InvestorProfile, ThemeIntent
from app.services.advisor_utils import as_str_list, bare_symbol, extract_json
from app.services.symbol_resolver_service import get_symbol_resolver_service
from app.utils.logging import get_logger

logger = get_logger(__name__)

_CLASSIFY_SYSTEM = """Classify Indian equity advisor prompts. Return ONLY valid JSON:
{
  "intent": "MARKET_RECOMMENDATION|PERSONALIZED_PORTFOLIO|THEME_DISCOVERY|COMPANY_RESEARCH|FOLLOW_UP|UNKNOWN",
  "capital": null or explicit string ONLY if user stated amount,
  "time_horizon": null or explicit string ONLY if user stated horizon,
  "risk_appetite": null or explicit string ONLY if user stated risk,
  "market_cap_preference": null or explicit,
  "dividend_growth_preference": null or explicit,
  "investment_style": null or explicit,
  "preferences": [] only if user explicitly stated,
  "avoidances": [] only if user explicitly stated exclusions,
  "themes": [] only for THEME_DISCOVERY with explicit sectors/themes,
  "search_queries": ["provider search phrases appropriate to intent"],
  "company_symbol": null or ticker if COMPANY_RESEARCH,
  "company_name": null or name if COMPANY_RESEARCH
}

CRITICAL: Use null or [] when NOT explicitly stated. NEVER invent risk, themes, avoidances, or preferences.

Intent guide:
- MARKET_RECOMMENDATION: broad top/best picks without personal capital/risk (e.g. top 5 companies 2026)
- THEME_DISCOVERY: sector/theme focus (AI, defence, dividend) without full portfolio details
- PERSONALIZED_PORTFOLIO: user states capital and/or risk and/or horizon
- COMPANY_RESEARCH: asks about one specific company/ticker
- FOLLOW_UP: refers to prior answer without new criteria"""


class AdvisorIntentType(StrEnum):
    MARKET_RECOMMENDATION = "MARKET_RECOMMENDATION"
    PERSONALIZED_PORTFOLIO = "PERSONALIZED_PORTFOLIO"
    THEME_DISCOVERY = "THEME_DISCOVERY"
    COMPANY_RESEARCH = "COMPANY_RESEARCH"
    FOLLOW_UP = "FOLLOW_UP"
    UNKNOWN = "UNKNOWN"


MARKET_ASSUMPTIONS = [
    "Balanced long-term research lens (no user risk/capital/horizon provided).",
    "Preference for large/mid-cap quality names with sector diversity.",
    "Fundamental quality and reasonable valuation weighted over speculative themes.",
]


class ClassifiedIntent(BaseModel):
    intent: AdvisorIntentType
    profile: InvestorProfile
    themes: list[ThemeIntent] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    theme_keywords: list[str] = Field(default_factory=list)
    company_symbol: str | None = None
    company_name: str | None = None
    assumptions_used: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    user_provided_fields: list[str] = Field(default_factory=list)


class AdvisorIntentService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def classify(self, prompt: str) -> ClassifiedIntent:
        rule_intent = _classify_rule_based(prompt)
        llm_data = await self._classify_llm(prompt)
        intent = _resolve_intent(rule_intent, llm_data)

        profile, themes, user_fields = _build_profile(llm_data, intent)
        search_queries = as_str_list(llm_data.get("search_queries"))
        theme_keywords = [kw for t in themes for kw in t.keywords]

        assumptions: list[str] = []
        missing: list[str] = []

        if intent == AdvisorIntentType.MARKET_RECOMMENDATION:
            assumptions = list(MARKET_ASSUMPTIONS)
            missing = _missing_profile_fields(profile)
            if not search_queries:
                search_queries = [
                    "large cap quality NSE India",
                    "blue chip india stock",
                    "best indian companies NSE",
                ]
        elif intent == AdvisorIntentType.THEME_DISCOVERY:
            if not search_queries and theme_keywords:
                search_queries = [f"{kw} NSE India stock" for kw in theme_keywords[:6]]
            missing = ["capital", "time_horizon", "risk_appetite"]
        elif intent == AdvisorIntentType.PERSONALIZED_PORTFOLIO:
            missing = _missing_profile_fields(profile)
            if missing:
                assumptions.append(
                    "Partial profile provided; ranking uses stated fields and research defaults for gaps."
                )
            if not search_queries:
                search_queries = _personalized_queries(profile)
        elif intent == AdvisorIntentType.COMPANY_RESEARCH:
            sym = _nullable_str(llm_data.get("company_symbol")) or _extract_ticker(prompt)
            name = _nullable_str(llm_data.get("company_name"))
            return ClassifiedIntent(
                intent=intent,
                profile=profile,
                company_symbol=sym,
                company_name=name,
                search_queries=search_queries,
                user_provided_fields=user_fields,
            )

        company_symbol = _nullable_str(llm_data.get("company_symbol"))
        company_name = _nullable_str(llm_data.get("company_name"))

        logger.info("Advisor classified intent=%s user_fields=%s", intent, user_fields)

        return ClassifiedIntent(
            intent=intent,
            profile=profile,
            themes=themes,
            search_queries=search_queries[:10],
            theme_keywords=theme_keywords,
            company_symbol=company_symbol,
            company_name=company_name,
            assumptions_used=assumptions,
            missing_inputs=missing,
            user_provided_fields=user_fields,
        )

    async def _classify_llm(self, prompt: str) -> dict[str, Any]:
        # No skip_probe: this must go through the same verified-with-fallback
        # acquisition as the main report pipeline (see LLMManager.acquire) —
        # skip_probe returns the first model in the chain unverified when the
        # process-wide probe cache is cold, with no fallback if it's actually
        # unusable (wrong credits, deprecated model id, etc.).
        llm = await asyncio.to_thread(lambda: build_llm(self._settings))
        raw = await asyncio.to_thread(
            call_llm_with_retry,
            llm,
            f"{_CLASSIFY_SYSTEM}\n\nUSER PROMPT:\n{prompt}\n\nJSON:",
            settings=self._settings,
            label="advisor_llm.classify",
        )
        parsed = extract_json(raw)
        return parsed if isinstance(parsed, dict) else {}


def _classify_rule_based(prompt: str) -> AdvisorIntentType:
    lower = prompt.lower().strip()

    if _looks_like_company_research(lower):
        return AdvisorIntentType.COMPANY_RESEARCH

    has_capital = bool(re.search(r"₹|\brs\.?|\blakh|\bcrore|\b\d+\s*k\b", lower))
    has_risk = bool(re.search(r"\b(low|moderate|medium|high)\s+risk\b", lower))
    has_horizon = bool(re.search(r"\b\d+\s*(year|yr|month)\b", lower))
    has_theme = bool(
        re.search(
            r"\b(ai|artificial intelligence|defence|defense|dividend|banking|pharma|it|technology|theme)\b",
            lower,
        )
    )
    has_market_broad = bool(
        re.search(r"\btop\s*\d+|\bbest\s+(compan|stock)|\blist\s+out\b", lower)
    )

    if has_capital or (has_risk and has_horizon):
        return AdvisorIntentType.PERSONALIZED_PORTFOLIO
    if has_theme and not (has_capital or has_risk):
        return AdvisorIntentType.THEME_DISCOVERY
    if has_market_broad and not (has_capital or has_risk or has_horizon):
        return AdvisorIntentType.MARKET_RECOMMENDATION
    if has_theme:
        return AdvisorIntentType.THEME_DISCOVERY
    if has_market_broad:
        return AdvisorIntentType.MARKET_RECOMMENDATION
    return AdvisorIntentType.UNKNOWN


def _looks_like_company_research(lower: str) -> bool:
    if re.search(r"\b(research|analyze|analysis|tell me about|overview of)\b", lower):
        if re.search(r"\b(infy|infosys|reliance|tcs|hdfc|wipro|itc)\b", lower):
            return True
        if re.search(r"\b[a-z]{2,12}\s+(ltd|limited)\b", lower):
            return True
    if re.search(r"^(research|analyze)\s+", lower):
        return True
    return False


def _resolve_intent(rule: AdvisorIntentType, llm_data: dict[str, Any]) -> AdvisorIntentType:
    raw = str(llm_data.get("intent") or "").upper().replace(" ", "_")
    try:
        llm_intent = AdvisorIntentType(raw)
    except ValueError:
        llm_intent = AdvisorIntentType.UNKNOWN

    if rule != AdvisorIntentType.UNKNOWN:
        return rule
    if llm_intent != AdvisorIntentType.UNKNOWN:
        return llm_intent
    return AdvisorIntentType.MARKET_RECOMMENDATION


def _build_profile(
    data: dict[str, Any], intent: AdvisorIntentType
) -> tuple[InvestorProfile, list[ThemeIntent], list[str]]:
    user_fields: list[str] = []
    capital = _nullable_str(data.get("capital"))
    horizon = _nullable_str(data.get("time_horizon"))
    risk = _nullable_str(data.get("risk_appetite"))
    mcap = _nullable_str(data.get("market_cap_preference"))
    div_growth = _nullable_str(data.get("dividend_growth_preference"))
    style = _nullable_str(data.get("investment_style"))
    preferences = as_str_list(data.get("preferences"))
    avoidances = as_str_list(data.get("avoidances"))

    if capital:
        user_fields.append("capital")
    if horizon:
        user_fields.append("time_horizon")
    if risk:
        user_fields.append("risk_appetite")
    if mcap:
        user_fields.append("market_cap_preference")
    if div_growth:
        user_fields.append("dividend_growth_preference")
    if style:
        user_fields.append("investment_style")
    if preferences:
        user_fields.append("preferences")
    if avoidances:
        user_fields.append("avoidances")

    themes: list[ThemeIntent] = []
    if intent in (AdvisorIntentType.THEME_DISCOVERY, AdvisorIntentType.PERSONALIZED_PORTFOLIO):
        for item in data.get("themes") or []:
            if not isinstance(item, dict):
                continue
            themes.append(
                ThemeIntent(
                    name=str(item.get("name") or "Theme"),
                    keywords=as_str_list(item.get("keywords")),
                    related_sectors=as_str_list(item.get("related_sectors")),
                    inclusion_criteria=str(item.get("inclusion_criteria") or ""),
                    exclusion_criteria=str(item.get("exclusion_criteria") or ""),
                )
            )
        if themes:
            user_fields.append("themes")

    profile = InvestorProfile(
        capital=capital,
        time_horizon=horizon,
        risk_appetite=risk,
        preferences=preferences,
        avoidances=avoidances,
        market_cap_preference=mcap,
        dividend_growth_preference=div_growth,
        investment_style=style,
        themes=themes,
    )
    return profile, themes, user_fields


def _nullable_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "not available", "n/a", "unknown"}:
        return None
    return text


def _missing_profile_fields(profile: InvestorProfile) -> list[str]:
    missing = []
    if not profile.capital:
        missing.append("capital")
    if not profile.time_horizon:
        missing.append("time_horizon")
    if not profile.risk_appetite:
        missing.append("risk_appetite")
    return missing


def _personalized_queries(profile: InvestorProfile) -> list[str]:
    queries = ["quality indian large cap NSE"]
    if profile.risk_appetite and "low" in profile.risk_appetite.lower():
        queries.append("low risk blue chip india")
    elif profile.risk_appetite and "high" in profile.risk_appetite.lower():
        queries.append("growth mid cap india")
    return queries


def _extract_ticker(prompt: str) -> str | None:
    resolver = get_symbol_resolver_service()
    for token in re.findall(r"\b[A-Z]{2,12}\b", prompt.upper()):
        if token in {"NSE", "BSE", "INR", "AI", "IT"}:
            continue
        bare = bare_symbol(token)
        if resolver.resolve_bare(bare):
            return bare

    words = re.findall(r"[a-zA-Z][a-zA-Z0-9&.-]{1,}", prompt)
    for size in range(min(4, len(words)), 0, -1):
        for i in range(len(words) - size + 1):
            phrase = " ".join(words[i : i + size])
            resolved = resolver.resolve_one(phrase)
            if resolved:
                return resolved.symbol
    return None
