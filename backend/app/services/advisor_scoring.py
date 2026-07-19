"""Rule-based scoring for validated advisor candidates."""

from __future__ import annotations

from app.schemas.advisor import CandidateValidation
from app.schemas.financial import FinancialSummaryResponse
from app.services.advisor_utils import candidate_blob


def score_financial_quality(snap: FinancialSummaryResponse | None) -> int | None:
    if snap is None:
        return None
    score = 50
    if snap.roe is not None:
        if snap.roe >= 0.18:
            score += 20
        elif snap.roe >= 0.12:
            score += 10
        elif snap.roe < 0.05:
            score -= 15
    if snap.profit_margin is not None:
        if snap.profit_margin >= 0.15:
            score += 15
        elif snap.profit_margin < 0.05:
            score -= 10
    if snap.debt_to_equity is not None:
        if snap.debt_to_equity <= 0.5:
            score += 10
        elif snap.debt_to_equity > 1.5:
            score -= 15
    if snap.revenue_growth is not None and snap.revenue_growth > 0.08:
        score += 5
    return max(0, min(100, score))


def score_valuation(snap: FinancialSummaryResponse | None) -> int | None:
    if snap is None or snap.pe_ratio is None:
        return None
    pe = snap.pe_ratio
    if pe <= 0:
        return 40
    if 12 <= pe <= 28:
        return 75
    if pe < 12:
        return 65
    if pe <= 40:
        return 55
    return 35


def score_risk(snap: FinancialSummaryResponse | None, validation: CandidateValidation) -> int:
    base = 60
    if snap and snap.debt_to_equity is not None:
        if snap.debt_to_equity > 2:
            base -= 25
        elif snap.debt_to_equity > 1:
            base -= 10
    if validation.theme_match_score < 75:
        base -= 5
    return max(0, min(100, base))


def score_prior_report(prior_summary: str | None) -> int:
    return 70 if prior_summary else 40


def overall_match_score(
    validation: CandidateValidation,
    snap: FinancialSummaryResponse | None,
    prior_summary: str | None,
) -> int:
    theme = validation.theme_match_score
    fin = score_financial_quality(snap)
    val = score_valuation(snap)
    risk = score_risk(snap, validation)
    prior = score_prior_report(prior_summary)

    fin_w = (fin if fin is not None else 45) * 0.25
    val_w = (val if val is not None else 45) * 0.15
    total = (
        theme * 0.35
        + fin_w
        + val_w
        + risk * 0.15
        + prior * 0.10
    )
    if fin is None or val is None:
        total *= 0.92
    return max(0, min(100, int(round(total))))


def rule_theme_score(
    blob: str,
    theme_keywords: list[str],
    related_sectors: list[str],
    exclusion_criteria: str,
) -> tuple[int, list[str], list[str]]:
    """Keyword/sector rule score before LLM validation."""
    evidence: list[str] = []
    matched: list[str] = []
    hits = 0
    for kw in theme_keywords:
        if kw.lower() in blob:
            hits += 1
            evidence.append(f"Keyword match: {kw}")
    for sector in related_sectors:
        if sector.lower() in blob:
            hits += 1
            evidence.append(f"Sector alignment: {sector}")
            matched.append(sector)
    if hits == 0:
        return 0, matched, evidence

    # Generic industrial with no theme signal
    generic_only = any(
        x in blob for x in ("bank", "fmcg", "consumer goods", "insurance", "nbfc")
    ) and not any(kw.lower() in blob for kw in theme_keywords[:3])
    if generic_only and exclusion_criteria:
        return max(0, min(40, hits * 15)), matched, evidence

    score = min(100, 35 + hits * 12)
    return score, matched, evidence
