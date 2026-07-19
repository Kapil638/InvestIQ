"""Parse Agent 4 free-text output into structured recommendation."""

import re

from app.schemas.research import InvestmentRecommendation, RecommendationRating
from app.utils.logging import get_logger

logger = get_logger(__name__)

_RATING_FROM_LABEL = re.compile(
    r"\brating\s*[:\-]?\s*(buy|hold|avoid|watchlist)\b",
    re.IGNORECASE,
)

_RATING_FALLBACK_PATTERNS = [
    (r"\b(buy)\b", RecommendationRating.BUY),
    (r"\b(hold)\b", RecommendationRating.HOLD),
    (r"\b(avoid)\b", RecommendationRating.AVOID),
    (r"\b(watchlist)\b", RecommendationRating.WATCHLIST),
]

_RATING_WORD_MAP = {
    "buy": RecommendationRating.BUY,
    "hold": RecommendationRating.HOLD,
    "avoid": RecommendationRating.AVOID,
    "watchlist": RecommendationRating.WATCHLIST,
}


def parse_recommendation(raw: str) -> InvestmentRecommendation:
    rating = _extract_rating(raw)
    confidence = _extract_confidence(raw)
    reasoning = _extract_section(raw, ["reasoning", "rationale", "investment case"]) or raw[:2000]
    risks = _extract_bullet_list(raw, ["risks", "key risks", "risk factors"])
    target_price = _extract_line_value(raw, ["target price", "price target", "target price range"])
    horizon = _extract_line_value(raw, ["investment horizon", "horizon", "time horizon"])
    allocation = _extract_line_value(
        raw,
        ["portfolio allocation", "allocation suggestion", "allocation"],
    )

    return InvestmentRecommendation(
        rating=rating,
        confidence_score=0.0,
        reasoning=reasoning.strip(),
        risks=risks,
        target_price_range=target_price,
        investment_horizon=horizon,
        portfolio_allocation_suggestion=allocation,
        llm_suggested_confidence=confidence,
    )


def _extract_rating(text: str) -> RecommendationRating:
    label_match = _RATING_FROM_LABEL.search(text)
    if label_match:
        return _RATING_WORD_MAP[label_match.group(1).lower()]

    logger.warning(
        "Recommendation rating not found via 'Rating:' label, using fallback scan"
    )
    lower = text.lower()
    for pattern, rating in _RATING_FALLBACK_PATTERNS:
        if re.search(pattern, lower):
            return rating
    return RecommendationRating.HOLD


def _extract_confidence(text: str) -> float:
    match = re.search(r"confidence(?:\s*score)?[:\s]+(\d{1,3})", text, re.IGNORECASE)
    if match:
        return min(float(match.group(1)), 100.0)
    match = re.search(r"(\d{1,3})\s*%", text)
    if match:
        return min(float(match.group(1)), 100.0)
    return 50.0


def _extract_section(text: str, headers: list[str]) -> str | None:
    for header in headers:
        pattern = rf"{header}\s*[:\-]?\s*(.+?)(?:\n\s*\n|\n\d+\.|\n[A-Z][a-z]+:|\Z)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return None


def _extract_bullet_list(text: str, headers: list[str]) -> list[str]:
    section = _extract_section(text, headers)
    if not section:
        return []
    items = re.findall(r"[-*•]\s*(.+)", section)
    return [item.strip() for item in items if item.strip()]


def _extract_line_value(text: str, labels: list[str]) -> str | None:
    for label in labels:
        match = re.search(rf"{label}\s*[:\-]\s*(.+)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None
