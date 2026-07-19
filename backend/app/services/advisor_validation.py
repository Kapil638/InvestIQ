"""Evidence validation for advisor candidates."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from app.agents.llm import build_llm
from app.core.config import Settings
from app.llm.caller import call_llm_with_retry
from app.schemas.advisor import CandidateValidation, InvestorProfile, THEME_MATCH_THRESHOLD
from app.schemas.financial import FinancialSummaryResponse
from app.services.advisor_scoring import rule_theme_score, score_financial_quality
from app.services.advisor_utils import as_str_list, bare_symbol, candidate_blob, extract_json
from app.utils.logging import get_logger

logger = get_logger(__name__)

_VALIDATE_SYSTEM = """You validate whether Indian listed equity candidates match the user's investment themes.

Return ONLY valid JSON array (no markdown). One object per candidate:
{
  "symbol": "TICKER",
  "is_valid": true|false,
  "matched_themes": ["theme names"],
  "theme_match_score": 0-100,
  "evidence": ["specific factual evidence from provided data only"],
  "reason": "why it matches",
  "reject_reason": "if invalid, specific reason"
}

Reject (is_valid=false) when:
- theme_match_score < 60
- no concrete evidence from profile/sector/summary
- company is generic bank/FMCG/industrial with no theme exposure
- reason is vague or generic
- exclusion criteria clearly apply

Never invent business facts not present in the candidate data."""

_GENERIC_SECTORS = frozenset(
    {"financial services", "fmcg", "consumer goods", "banking", "insurance", "nbfc"}
)


@dataclass
class EnrichedCandidate:
    raw: RawCandidate
    industry: str | None = None
    business_summary: str | None = None
    snapshot: FinancialSummaryResponse | None = None
    prior_report_summary: str | None = None
    price_source: str | None = None
    fundamentals_source: str | None = None


class AdvisorValidator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def validate_all(
        self,
        profile: InvestorProfile,
        enriched: list[EnrichedCandidate],
    ) -> tuple[list[EnrichedCandidate], list[CandidateValidation]]:
        if not enriched:
            return [], []

        rule_scores = {e.raw.symbol: self._rule_prefilter(profile, e) for e in enriched}
        llm_validations = await self._llm_validate_batch(profile, enriched)

        validated: list[EnrichedCandidate] = []
        validations: list[CandidateValidation] = []
        rejected = 0

        for item in enriched:
            sym = item.raw.symbol
            llm_v = llm_validations.get(sym)
            rule_v = rule_scores.get(sym)
            merged = self._merge_validation(sym, rule_v, llm_v, profile)

            if merged.is_valid and merged.theme_match_score >= THEME_MATCH_THRESHOLD and merged.evidence:
                validated.append(item)
                validations.append(merged)
            else:
                rejected += 1
                logger.debug(
                    "Advisor rejected %s score=%s reason=%s",
                    sym,
                    merged.theme_match_score,
                    merged.reject_reason or merged.reason,
                )

        logger.info(
            "Advisor validation: input=%d validated=%d rejected=%d",
            len(enriched),
            len(validated),
            rejected,
        )
        return validated, validations

    async def validate_market(
        self, enriched: list[EnrichedCandidate]
    ) -> tuple[list[EnrichedCandidate], list[CandidateValidation]]:
        """Broad market-quality screen — no theme filter."""
        validated: list[EnrichedCandidate] = []
        validations: list[CandidateValidation] = []
        seen_sectors: set[str] = set()

        for item in enriched:
            snap = item.snapshot
            quality = score_financial_quality(snap)
            base_score = quality if quality is not None else 58
            if snap is None and quality is None:
                base_score = 55

            sector = (item.raw.sector or (snap.sector if snap else None) or "Unknown").strip()
            diversity_bonus = 5 if sector not in seen_sectors else 0
            seen_sectors.add(sector)
            score = min(100, max(60, base_score + diversity_bonus))

            evidence = [f"Sector: {sector}"]
            if snap and snap.roe is not None:
                evidence.append(f"ROE data available from {snap.fundamentals_source or snap.data_source}")
            if item.prior_report_summary:
                evidence.append("Prior InvestIQ report available")

            val = CandidateValidation(
                symbol=item.raw.symbol,
                is_valid=True,
                matched_themes=["market quality"],
                theme_match_score=score,
                evidence=evidence,
                reason="Passes broad market-quality research screen.",
            )
            validated.append(item)
            validations.append(val)

        logger.info("Advisor market validation: input=%d validated=%d", len(enriched), len(validated))
        return validated, validations

    def _rule_prefilter(
        self, profile: InvestorProfile, item: EnrichedCandidate
    ) -> CandidateValidation:
        blob = candidate_blob(
            item.raw.company_name,
            item.raw.symbol,
            item.raw.sector,
            item.industry,
            item.business_summary,
        )
        if not profile.themes:
            return CandidateValidation(
                symbol=item.raw.symbol,
                is_valid=True,
                matched_themes=["general"],
                theme_match_score=70,
                evidence=["No specific theme filter requested."],
                reason="General candidate.",
            )

        best_score = 0
        best_evidence: list[str] = []
        matched_names: list[str] = []
        for theme in profile.themes:
            score, sectors, evidence = rule_theme_score(
                blob, theme.keywords, theme.related_sectors, theme.exclusion_criteria
            )
            if score > best_score:
                best_score = score
                best_evidence = evidence
                matched_names = [theme.name] if score >= 40 else []
                if sectors:
                    matched_names.extend(sectors[:2])

        is_valid = best_score >= THEME_MATCH_THRESHOLD and bool(best_evidence)
        reject = None
        if not is_valid:
            if _is_unrelated_sector(blob, profile):
                reject = "Sector/profile does not align with requested themes."
            elif best_score < THEME_MATCH_THRESHOLD:
                reject = "Insufficient theme keyword or sector evidence."
            else:
                reject = "No concrete evidence for theme match."

        return CandidateValidation(
            symbol=item.raw.symbol,
            is_valid=is_valid,
            matched_themes=matched_names,
            theme_match_score=best_score,
            evidence=best_evidence,
            reason="Rule-based theme alignment." if is_valid else "",
            reject_reason=reject,
        )

    async def _llm_validate_batch(
        self,
        profile: InvestorProfile,
        enriched: list[EnrichedCandidate],
    ) -> dict[str, CandidateValidation]:
        if not profile.themes:
            return {}

        payload = []
        for e in enriched[:20]:
            payload.append(
                {
                    "symbol": e.raw.symbol,
                    "company_name": e.raw.company_name,
                    "sector": e.raw.sector,
                    "industry": e.industry,
                    "business_summary": e.business_summary or "Not available",
                    "prior_report": e.prior_report_summary,
                }
            )

        themes_block = [t.model_dump() for t in profile.themes]
        prompt = (
            f"{_VALIDATE_SYSTEM}\n\n"
            f"USER THEMES:\n{json.dumps(themes_block, indent=2)}\n\n"
            f"AVOIDANCES:\n{json.dumps(profile.avoidances)}\n\n"
            f"CANDIDATES:\n{json.dumps(payload, indent=2)}\n\n"
            "JSON array:"
        )

        llm = await asyncio.to_thread(lambda: build_llm(self._settings, skip_probe=True))
        raw = await asyncio.to_thread(
            call_llm_with_retry,
            llm,
            prompt,
            settings=self._settings,
            label="advisor_llm.validate",
        )
        parsed = extract_json(raw)
        out: dict[str, CandidateValidation] = {}
        if not isinstance(parsed, list):
            return out

        for item in parsed:
            if not isinstance(item, dict):
                continue
            sym = bare_symbol(str(item.get("symbol") or ""))
            if not sym:
                continue
            try:
                out[sym] = CandidateValidation(
                    symbol=sym,
                    is_valid=bool(item.get("is_valid")),
                    matched_themes=as_str_list(item.get("matched_themes")),
                    theme_match_score=max(0, min(100, int(item.get("theme_match_score") or 0))),
                    evidence=as_str_list(item.get("evidence")),
                    reason=str(item.get("reason") or ""),
                    reject_reason=item.get("reject_reason"),
                )
            except (TypeError, ValueError):
                continue
        return out

    def _merge_validation(
        self,
        symbol: str,
        rule: CandidateValidation | None,
        llm: CandidateValidation | None,
        profile: InvestorProfile,
    ) -> CandidateValidation:
        if llm is None and rule is None:
            return CandidateValidation(symbol=symbol, is_valid=False, reject_reason="No validation data")

        if llm is None:
            return rule or CandidateValidation(symbol=symbol, is_valid=False)

        if rule is None:
            return llm

        # Both must agree for thematic prompts
        if profile.themes:
            score = min(rule.theme_match_score, llm.theme_match_score)
            if rule.theme_match_score < THEME_MATCH_THRESHOLD or llm.theme_match_score < THEME_MATCH_THRESHOLD:
                return CandidateValidation(
                    symbol=symbol,
                    is_valid=False,
                    matched_themes=llm.matched_themes or rule.matched_themes,
                    theme_match_score=score,
                    evidence=llm.evidence or rule.evidence,
                    reason=llm.reason,
                    reject_reason=llm.reject_reason or rule.reject_reason or "Theme threshold not met",
                )
            is_valid = rule.is_valid and llm.is_valid and bool(llm.evidence or rule.evidence)
            return CandidateValidation(
                symbol=symbol,
                is_valid=is_valid,
                matched_themes=list(dict.fromkeys(llm.matched_themes + rule.matched_themes)),
                theme_match_score=score,
                evidence=list(dict.fromkeys(llm.evidence + rule.evidence))[:6],
                reason=llm.reason or rule.reason,
                reject_reason=None if is_valid else (llm.reject_reason or rule.reject_reason),
            )

        return llm


def _is_unrelated_sector(blob: str, profile: InvestorProfile) -> bool:
    theme_blob = " ".join(
        kw for t in profile.themes for kw in t.keywords + t.related_sectors
    ).lower()
    if any(k in theme_blob for k in ("defence", "defense", "aerospace", "ai", "artificial intelligence")):
        if any(s in blob for s in _GENERIC_SECTORS) and not any(
            k in blob for k in ("defence", "defense", "aerospace", "radar", "missile", "ai", "software", "technology")
        ):
            return True
    return False
