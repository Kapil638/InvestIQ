"""Deterministic investment committee scoring – not LLM-derived."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.agent_outputs import AnalysisOutput, RiskOutput
from app.schemas.financial import FinancialResearchResponse, FinancialRatios
from app.schemas.news import NewsResearchResponse
from app.schemas.research import (
    GuardrailResult,
    RecommendationRating,
    ResearchReportResponse,
    ScoreBreakdown,
    StructuredRiskAssessment,
)
from app.services.data_snapshot import compute_data_snapshot_hash
from app.utils.logging import get_logger

logger = get_logger(__name__)

SCORING_VERSION = "v1"
SCORING_VERSION_V2 = "v2"

WEIGHTS: dict[str, float] = {
    "financial_quality_score": 0.25,
    "valuation_score": 0.20,
    "growth_score": 0.20,
    "risk_score": 0.15,
    "news_score": 0.10,
    "data_quality_score": 0.10,
}

WEIGHTS_V2: dict[str, float] = {
    "growth": 0.20,
    "profitability": 0.20,
    "valuation": 0.15,
    "financial_health": 0.15,
    "management": 0.10,
    "sector_strength": 0.10,
    "news": 0.05,
    "risk": 0.05,
}

_BULLISH = re.compile(
    r"\b(growth|strong|outperform|bullish|upside|beat|expansion|robust|improving|positive)\b",
    re.I,
)
_BEARISH = re.compile(
    r"\b(decline|weak|risk|bearish|downside|pressure|concern|slowdown|debt|volatile|lawsuit)\b",
    re.I,
)


@dataclass(frozen=True)
class ScoringResult:
    confidence_score: int
    score_breakdown: ScoreBreakdown
    rating: RecommendationRating
    scoring_version: str
    data_snapshot_hash: str
    confidence_change_reason: str | None = None
    reused_prior_scoring: bool = False


class InvestmentScoringService:
    """Compute reproducible confidence and rating from structured report signals."""

    def score(
        self,
        report: ResearchReportResponse,
        *,
        structured_risks: StructuredRiskAssessment | None = None,
        previous_report: ResearchReportResponse | None = None,
    ) -> ScoringResult:
        data_hash = report.data_snapshot_hash or compute_data_snapshot_hash(
            report.ticker, report.financial_data, report.news_data
        )

        if (
            previous_report
            and previous_report.data_snapshot_hash == data_hash
            and previous_report.confidence_score is not None
            and previous_report.score_breakdown is not None
        ):
            logger.info(
                "Reusing prior deterministic scoring for %s hash=%s",
                report.ticker,
                data_hash,
            )
            return ScoringResult(
                confidence_score=previous_report.confidence_score,
                score_breakdown=previous_report.score_breakdown,
                rating=_rating_from_confidence(previous_report.confidence_score),
                scoring_version=previous_report.scoring_version or SCORING_VERSION,
                data_snapshot_hash=data_hash,
                reused_prior_scoring=True,
            )

        breakdown = self._compute_breakdown(report, structured_risks)
        version = SCORING_VERSION
        if report.analysis_output and report.risk_output:
            breakdown, confidence_raw = self._compute_v2(report)
            version = SCORING_VERSION_V2
        else:
            confidence_raw = self._weighted_confidence(breakdown, report.guardrails)

        confidence = self._apply_guardrail_penalties(confidence_raw, report.guardrails)
        confidence = max(0, min(100, int(round(confidence))))

        change_reason = self._confidence_change_reason(
            report.ticker,
            confidence,
            previous_report,
            data_hash,
        )

        if previous_report and previous_report.confidence_score is not None:
            delta = abs(confidence - previous_report.confidence_score)
            if delta > 10:
                logger.warning(
                    "Large confidence swing detected for %s: %s -> %s (delta=%s)",
                    report.ticker,
                    previous_report.confidence_score,
                    confidence,
                    delta,
                )

        rating = _rating_from_confidence(confidence)
        logger.info(
            "Deterministic scoring %s hash=%s confidence=%s rating=%s breakdown=%s",
            report.ticker,
            data_hash,
            confidence,
            rating.value,
            breakdown.model_dump(),
        )

        return ScoringResult(
            confidence_score=confidence,
            score_breakdown=breakdown,
            rating=rating,
            scoring_version=version,
            data_snapshot_hash=data_hash,
            confidence_change_reason=change_reason,
        )

    def _compute_v2(self, report: ResearchReportResponse) -> tuple[ScoreBreakdown, float]:
        assert report.analysis_output is not None
        assert report.risk_output is not None
        a = report.analysis_output.scores
        r = report.risk_output.scores
        risk_component = max(0, min(100, 100 - r.overall_risk))
        news_component = _score_news(report.news_data, report.news_research_summary)
        data_quality = _score_data_quality(
            report.financial_data, report.news_data, report.guardrails
        )

        weighted = (
            a.growth * WEIGHTS_V2["growth"]
            + a.profitability * WEIGHTS_V2["profitability"]
            + a.valuation * WEIGHTS_V2["valuation"]
            + a.financial_health * WEIGHTS_V2["financial_health"]
            + a.management * WEIGHTS_V2["management"]
            + a.sector_strength * WEIGHTS_V2["sector_strength"]
            + news_component * WEIGHTS_V2["news"]
            + risk_component * WEIGHTS_V2["risk"]
        )
        if report.guardrails and not report.guardrails.passed:
            weighted *= 0.85

        breakdown = ScoreBreakdown(
            financial_quality_score=(a.financial_health + a.profitability) // 2,
            valuation_score=a.valuation,
            growth_score=a.growth,
            risk_score=risk_component,
            news_score=news_component,
            data_quality_score=data_quality,
        )
        return breakdown, weighted

    def _compute_breakdown(
        self,
        report: ResearchReportResponse,
        structured_risks: StructuredRiskAssessment | None,
    ) -> ScoreBreakdown:
        fin = report.financial_data
        news = report.news_data
        ratios = _latest_ratios(fin)

        financial_quality = _score_financial_quality(fin, ratios)
        valuation = _score_valuation(fin, ratios)
        growth = _score_growth(fin, ratios)
        risk = _score_risk(structured_risks, report.guardrails, fin, ratios)
        news_score = _score_news(news, report.news_research_summary)
        data_quality = _score_data_quality(fin, news, report.guardrails)

        return ScoreBreakdown(
            financial_quality_score=financial_quality,
            valuation_score=valuation,
            growth_score=growth,
            risk_score=risk,
            news_score=news_score,
            data_quality_score=data_quality,
        )

    def _weighted_confidence(
        self, breakdown: ScoreBreakdown, guardrails: GuardrailResult | None
    ) -> float:
        scores = {
            "financial_quality_score": breakdown.financial_quality_score,
            "valuation_score": breakdown.valuation_score,
            "growth_score": breakdown.growth_score,
            "risk_score": breakdown.risk_score,
            "news_score": breakdown.news_score,
            "data_quality_score": breakdown.data_quality_score,
        }
        total = sum(scores[key] * WEIGHTS[key] for key in WEIGHTS)
        if guardrails and not guardrails.passed:
            total *= 0.85
        return total

    def _apply_guardrail_penalties(
        self, confidence: float, guardrails: GuardrailResult | None
    ) -> float:
        if not guardrails or not guardrails.issues:
            return confidence
        penalty = 0
        for issue in guardrails.issues:
            if issue.severity == "error":
                penalty += 8
            elif issue.severity == "warning":
                penalty += 3
        return confidence - penalty

    def _confidence_change_reason(
        self,
        ticker: str,
        confidence: int,
        previous_report: ResearchReportResponse | None,
        data_hash: str,
    ) -> str | None:
        if not previous_report or previous_report.confidence_score is None:
            return None
        prev = previous_report.confidence_score
        if abs(confidence - prev) <= 1:
            return None
        if previous_report.data_snapshot_hash == data_hash:
            return (
                f"Confidence adjusted from {prev}% to {confidence}% after committee "
                "re-scoring on unchanged underlying data."
            )
        return (
            f"Confidence changed from {prev}% to {confidence}% because refreshed "
            f"financial/news data altered the score breakdown for {ticker}."
        )


def _rating_from_confidence(score: int) -> RecommendationRating:
    if score >= 75:
        return RecommendationRating.BUY
    if score >= 55:
        return RecommendationRating.HOLD
    if score >= 35:
        return RecommendationRating.AVOID  # SELL band mapped to AVOID enum
    return RecommendationRating.AVOID


def _latest_ratios(fin: FinancialResearchResponse | None) -> FinancialRatios | None:
    if not fin or not fin.ratios:
        return None
    return fin.ratios[0]


def _score_financial_quality(
    fin: FinancialResearchResponse | None, ratios: FinancialRatios | None
) -> int:
    if fin is None:
        return 40
    score = 52
    roe = ratios.return_on_equity if ratios else None
    if roe is not None:
        if roe >= 0.18:
            score += 22
        elif roe >= 0.12:
            score += 12
        elif roe < 0.05:
            score -= 12
    npm = ratios.net_profit_margin if ratios else None
    if npm is not None:
        if npm >= 0.15:
            score += 12
        elif npm < 0.05:
            score -= 10
    dte = ratios.debt_to_equity if ratios else None
    if dte is not None:
        if dte <= 0.5:
            score += 8
        elif dte > 1.5:
            score -= 14
    if fin.warnings:
        score -= min(10, len(fin.warnings) * 3)
    return max(0, min(100, score))


def _score_valuation(
    fin: FinancialResearchResponse | None, ratios: FinancialRatios | None
) -> int:
    pe = None
    if ratios and ratios.price_to_earnings is not None:
        pe = ratios.price_to_earnings
    elif fin and fin.key_metrics and fin.key_metrics[0].pe_ratio is not None:
        pe = fin.key_metrics[0].pe_ratio
    if pe is None:
        return 50
    if pe <= 0:
        return 38
    if 12 <= pe <= 28:
        return 72
    if pe < 12:
        return 64
    if pe <= 40:
        return 56
    return 38


def _score_growth(
    fin: FinancialResearchResponse | None, ratios: FinancialRatios | None
) -> int:
    score = 55
    if not fin or not fin.income_statements or len(fin.income_statements) < 2:
        return score
    latest = fin.income_statements[0].revenue
    prior = fin.income_statements[1].revenue
    if latest is not None and prior and prior > 0:
        growth = (latest - prior) / prior
        if growth >= 0.15:
            score += 22
        elif growth >= 0.05:
            score += 10
        elif growth < 0:
            score -= 15
    return max(0, min(100, score))


def _score_risk(
    structured_risks: StructuredRiskAssessment | None,
    guardrails: GuardrailResult | None,
    fin: FinancialResearchResponse | None,
    ratios: FinancialRatios | None,
) -> int:
    score = 68
    risk_count = structured_risks.risk_count if structured_risks else 0
    score -= min(24, risk_count * 4)
    if guardrails and guardrails.issues:
        score -= min(15, sum(4 if i.severity == "error" else 2 for i in guardrails.issues))
    dte = ratios.debt_to_equity if ratios else None
    if dte is not None and dte > 2:
        score -= 12
    elif dte is not None and dte > 1:
        score -= 6
    if fin and fin.profile and fin.profile.beta and fin.profile.beta > 1.4:
        score -= 5
    return max(0, min(100, score))


def _score_news(news: NewsResearchResponse | None, summary: str | None) -> int:
    text = summary or ""
    if news and news.sentiment_summary:
        text += "\n" + news.sentiment_summary
    if not text.strip():
        return 48
    bull = len(_BULLISH.findall(text))
    bear = len(_BEARISH.findall(text))
    score = 55
    if bull > bear + 1:
        score += 18
    elif bear > bull + 1:
        score -= 18
    if news and news.warnings:
        score -= min(12, len(news.warnings) * 4)
    return max(0, min(100, score))


def _score_data_quality(
    fin: FinancialResearchResponse | None,
    news: NewsResearchResponse | None,
    guardrails: GuardrailResult | None,
) -> int:
    score = 50
    if fin:
        score += 15
        if fin.income_statements:
            score += 8
        if fin.ratios:
            score += 8
        if fin.market_data:
            score += 5
    if news:
        score += 10
        if news.latest_news:
            score += min(8, len(news.latest_news))
    if guardrails and guardrails.passed:
        score += 6
    missing = 0
    if not fin:
        missing += 1
    if not news:
        missing += 1
    score -= missing * 18
    return max(0, min(100, score))
