"""Post-LLM guardrails for advisor recommendations."""

from __future__ import annotations

from app.schemas.advisor import (
    ADVISOR_DISCLAIMER,
    CandidateValidation,
    StockRecommendation,
    THEME_MATCH_THRESHOLD,
)
from app.services.advisor_utils import bare_symbol, sanitize_text_list


def apply_guardrails(
    recommendations: list[StockRecommendation],
    validations: dict[str, CandidateValidation],
    allowed_symbols: set[str],
    *,
    require_themes: bool = True,
) -> list[StockRecommendation]:
    safe: list[StockRecommendation] = []
    for rec in recommendations:
        sym = bare_symbol(rec.symbol)
        if sym not in allowed_symbols:
            continue
        val = validations.get(sym)
        if val is None:
            continue
        if val.theme_match_score < THEME_MATCH_THRESHOLD:
            continue
        if not rec.matched_themes and val.matched_themes:
            rec.matched_themes = val.matched_themes
        if require_themes and not rec.matched_themes:
            continue
        if not rec.theme_match_reason or rec.theme_match_reason == "Not available":
            rec.theme_match_reason = val.reason or "Theme alignment based on validated evidence."
        if not rec.key_evidence and val.evidence:
            rec.key_evidence = val.evidence
        if not rec.key_risks:
            rec.key_risks = ["Market and sector risks apply."]
        rec.why_it_fits = sanitize_text_list(rec.why_it_fits)
        rec.key_risks = sanitize_text_list(rec.key_risks)
        rec.key_evidence = sanitize_text_list(rec.key_evidence)
        safe.append(rec)
    return safe


def ensure_disclaimer(disclaimer: str | None) -> str:
    return disclaimer or ADVISOR_DISCLAIMER
