"""Tests for recommendation_parser rating extraction."""

from app.guardrails.recommendation_parser import parse_recommendation
from app.schemas.research import RecommendationRating


def test_extract_rating_prefers_rating_label_over_prose_buy() -> None:
    raw = """
    Rating: Hold
    Confidence Score: 65
    Reasoning: Valuation is stretched; avoid new buys until multiples compress.
    """
    rec = parse_recommendation(raw)
    assert rec.rating == RecommendationRating.HOLD


def test_extract_rating_falls_back_to_whole_text_scan_without_label() -> None:
    raw = """
    Confidence Score: 72
    Reasoning: Strong fundamentals support a buy thesis for long-term holders.
    """
    rec = parse_recommendation(raw)
    assert rec.rating == RecommendationRating.BUY
