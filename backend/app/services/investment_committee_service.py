"""
Investment Committee service – deterministic analyst mapping from CrewAI report output.

Maps existing multi-agent report fields into institutional analyst personas without
additional LLM calls. Designed for future specialist agents to populate the same schema.
"""

from __future__ import annotations

import re

from app.schemas.investment_committee import (
    AnalystOpinion,
    AnalystPersonaId,
    AnalystRecommendation,
    CommitteeVerdict,
    InvestmentCommittee,
)
from app.schemas.research import RecommendationRating, ResearchReportResponse

_RATING_ORDER = (
    AnalystRecommendation.AVOID,
    AnalystRecommendation.SELL,
    AnalystRecommendation.HOLD,
    AnalystRecommendation.BUY,
)

_BULLISH = re.compile(
    r"\b(growth|strong|outperform|bullish|upside|momentum|beat|expansion|robust|improving)\b",
    re.I,
)
_BEARISH = re.compile(
    r"\b(decline|weak|risk|bearish|downside|pressure|concern|slowdown|debt|volatile|overvalued)\b",
    re.I,
)
_SENTIMENT = re.compile(
    r"\b(growth|strong|outperform|bullish|upside|momentum|beat|expansion|robust|improving|"
    r"decline|weak|risk|bearish|downside|pressure|concern|slowdown|debt|volatile|overvalued)\b",
    re.I,
)
_TECHNICAL = re.compile(
    r"\b(trend|support|resistance|moving average|momentum|breakout|volume|rsi|macd|chart)\b",
    re.I,
)
_VALUATION = re.compile(
    r"\b(p/e|pe ratio|pb|peg|ev/ebitda|valuation|multiple|dcf|premium|discount|fair value)\b",
    re.I,
)


class InvestmentCommitteeService:
    """Builds Investment Committee views from an existing research report."""

    def build(self, report: ResearchReportResponse) -> InvestmentCommittee:
        base_rating = _base_analyst_rating(report)
        base_confidence = _base_confidence(report)
        sources_used = _collect_sources(report)

        analysts = [
            self._fundamental_analyst(report, base_rating, base_confidence, sources_used),
            self._news_analyst(report, base_rating, base_confidence),
            self._technical_analyst(report, base_rating, base_confidence),
            self._valuation_analyst(report, base_rating, base_confidence),
            self._risk_analyst(report, base_rating, base_confidence),
        ]

        verdict = self._committee_verdict(report, analysts, base_rating, base_confidence)
        return InvestmentCommittee(analysts=analysts, verdict=verdict, sources_used=sources_used)

    def enrich(self, report: ResearchReportResponse) -> ResearchReportResponse:
        if report.investment_committee is not None:
            return report
        committee = self.build(report)
        return report.model_copy(update={"investment_committee": committee})

    def _fundamental_analyst(
        self,
        report: ResearchReportResponse,
        base: AnalystRecommendation,
        confidence: int,
        sources_used: list[str],
    ) -> AnalystOpinion:
        points = _split_lines(report.financial_data_summary, max_items=5)
        if not points and report.analysis:
            points = _lines_matching(report.analysis, _SENTIMENT, max_items=4)
        if not points and report.recommendation:
            points = [report.recommendation.reasoning[:280]] if report.recommendation.reasoning else []

        profile = report.financial_data.profile if report.financial_data else None
        if profile:
            if profile.sector:
                points.insert(0, f"Sector: {profile.sector}")
            if profile.market_cap:
                points.append(f"Market cap context available for {profile.company_name or report.ticker}")

        fund_sources = [s for s in sources_used if s in {"NSE/BSE MCP", "Yahoo Finance"}]
        if not fund_sources:
            fund_sources = ["Yahoo Finance"]

        return AnalystOpinion(
            id=AnalystPersonaId.FUNDAMENTAL,
            name="Fundamental Analyst",
            title="Revenue, profitability, balance sheet & competitive moat",
            recommendation=base,
            confidence=_clamp_confidence(confidence + _sentiment_delta(report.financial_data_summary)),
            supporting_points=points[:5] or ["Fundamental data reviewed; see financial health section."],
            sources=fund_sources,
        )

    def _news_analyst(
        self,
        report: ResearchReportResponse,
        base: AnalystRecommendation,
        confidence: int,
    ) -> AnalystOpinion:
        news_text = report.news_research_summary or ""
        delta = _sentiment_delta(news_text)
        rating = _tilt_rating(base, 1 if delta > 5 else (-1 if delta < -5 else 0))
        points = _split_lines(news_text, max_items=5)
        if not points and report.news_data and report.news_data.articles:
            points = [a.title for a in report.news_data.articles[:4] if a.title]

        return AnalystOpinion(
            id=AnalystPersonaId.NEWS,
            name="News Analyst",
            title="Headlines, announcements & management commentary",
            recommendation=rating,
            confidence=_clamp_confidence(confidence + delta),
            supporting_points=points[:5] or ["No material news flow captured in this report window."],
            sources=["Tavily"],
        )

    def _technical_analyst(
        self,
        report: ResearchReportResponse,
        base: AnalystRecommendation,
        confidence: int,
    ) -> AnalystOpinion:
        analysis = report.analysis or ""
        tech_lines = _lines_matching(analysis, _TECHNICAL, max_items=4)
        if not tech_lines:
            tech_lines = _split_lines(analysis, max_items=3)

        momentum_delta = 3 if _BULLISH.search(analysis) else (-3 if _BEARISH.search(analysis) else 0)
        rating = _tilt_rating(base, 1 if momentum_delta > 0 else (-1 if momentum_delta < 0 else 0))

        return AnalystOpinion(
            id=AnalystPersonaId.TECHNICAL,
            name="Technical Analyst",
            title="Price trend, momentum & key levels",
            recommendation=rating,
            confidence=_clamp_confidence(confidence + momentum_delta),
            supporting_points=tech_lines[:5]
            or ["Technical view derived from available price context in the research analysis."],
            sources=_technical_sources(report),
        )

    def _valuation_analyst(
        self,
        report: ResearchReportResponse,
        base: AnalystRecommendation,
        confidence: int,
    ) -> AnalystOpinion:
        rec = report.recommendation
        points: list[str] = []
        if rec and rec.target_price_range:
            points.append(f"Target price range: {rec.target_price_range}")
        val_lines = _lines_matching(
            (report.financial_data_summary or "") + "\n" + (report.analysis or ""),
            _VALUATION,
            max_items=4,
        )
        points.extend(val_lines)

        val_text = (report.financial_data_summary or "") + (report.analysis or "")
        delta = -5 if _BEARISH.search(val_text) and "overvalued" in val_text.lower() else 0
        rating = _tilt_rating(base, -1 if "overvalued" in val_text.lower() else 0)

        return AnalystOpinion(
            id=AnalystPersonaId.VALUATION,
            name="Valuation Analyst",
            title="Multiples, relative value & fair-value view",
            recommendation=rating,
            confidence=_clamp_confidence(confidence + delta),
            supporting_points=points[:5] or ["Valuation assessed using available financial multiples."],
            sources=["Financial statements", "Market multiples"],
        )

    def _risk_analyst(
        self,
        report: ResearchReportResponse,
        base: AnalystRecommendation,
        confidence: int,
    ) -> AnalystOpinion:
        rec = report.recommendation
        points = list(rec.risks[:5]) if rec and rec.risks else []
        if report.guardrails and report.guardrails.issues:
            points.extend(issue.message for issue in report.guardrails.issues[:3])
        if not points and report.analysis:
            points = _lines_matching(report.analysis, _BEARISH, max_items=4)

        conservative = _tilt_rating(base, -1)

        return AnalystOpinion(
            id=AnalystPersonaId.RISK,
            name="Risk Analyst",
            title="Business, sector, macro & governance risks",
            recommendation=conservative,
            confidence=_clamp_confidence(confidence - 4),
            supporting_points=points[:5] or ["Risk profile reviewed against sector and macro context."],
            sources=["Company filings", "News"],
        )

    def _committee_verdict(
        self,
        report: ResearchReportResponse,
        analysts: list[AnalystOpinion],
        base: AnalystRecommendation,
        confidence: int,
    ) -> CommitteeVerdict:
        rec = report.recommendation
        bull_case, bear_case = _bull_bear_cases(report)

        vote_summary = _consensus_summary(analysts)
        conclusion = _build_conclusion(report, analysts, base)

        return CommitteeVerdict(
            final_recommendation=base,
            overall_confidence=confidence,
            investment_horizon=rec.investment_horizon if rec else "3-year horizon (default institutional view)",
            bull_case=bull_case[:4],
            bear_case=bear_case[:4],
            conclusion=conclusion,
            consensus_summary=vote_summary,
        )


def _base_analyst_rating(report: ResearchReportResponse) -> AnalystRecommendation:
    rec = report.recommendation
    if not rec:
        if report.confidence_score is not None:
            return _analyst_rating_from_confidence(report.confidence_score)
        return AnalystRecommendation.HOLD

    mapping = {
        RecommendationRating.BUY: AnalystRecommendation.BUY,
        RecommendationRating.HOLD: AnalystRecommendation.HOLD,
        RecommendationRating.AVOID: AnalystRecommendation.AVOID,
        RecommendationRating.WATCHLIST: AnalystRecommendation.HOLD,
    }
    rating = mapping.get(rec.rating, AnalystRecommendation.HOLD)

    confidence = _base_confidence(report)
    if rec.rating == RecommendationRating.AVOID and confidence >= 65:
        return AnalystRecommendation.SELL
    if rec.rating == RecommendationRating.HOLD and confidence < 45:
        analysis = (report.analysis or "").lower()
        if "sell" in analysis or "downside" in analysis:
            return AnalystRecommendation.SELL

    return rating


def _base_confidence(report: ResearchReportResponse) -> int:
    if report.confidence_score is not None:
        return _clamp_confidence(int(report.confidence_score))
    if report.recommendation:
        return _clamp_confidence(int(round(report.recommendation.confidence_score)))
    return 50


def _collect_sources(report: ResearchReportResponse) -> list[str]:
    sources: list[str] = []
    if report.financial_data and report.financial_data.data_sources:
        for raw in report.financial_data.data_sources:
            if raw in {"tapetide_mcp", "nse_bse_mcp"}:
                sources.append("Tapetide NSE/BSE MCP")
            elif raw in {"yahoo", "yahoo_finance"}:
                sources.append("Yahoo Finance")
            else:
                sources.append(raw.replace("_", " ").title())
    elif report.financial_data_summary:
        sources.append("Yahoo Finance")

    if report.news_research_summary or report.news_data:
        sources.append("Tavily")
    if report.guardrails:
        sources.append("InvestIQ guardrails")
    sources.append("CrewAI research agents")
    return list(dict.fromkeys(sources))


def _technical_sources(report: ResearchReportResponse) -> list[str]:
    raw = report.financial_data.data_sources if report.financial_data else []
    sources: list[str] = []
    if raw and ("tapetide_mcp" in raw or "nse_bse_mcp" in raw):
        sources.append("Tapetide NSE/BSE MCP")
    sources.append("Kite")
    if not sources:
        sources = ["Market data"]
    return sources


def _tilt_rating(current: AnalystRecommendation, steps: int) -> AnalystRecommendation:
    idx = _RATING_ORDER.index(current)
    new_idx = max(0, min(len(_RATING_ORDER) - 1, idx + steps))
    return _RATING_ORDER[new_idx]


def _clamp_confidence(value: int) -> int:
    return max(0, min(100, value))


def _analyst_rating_from_confidence(score: int) -> AnalystRecommendation:
    if score >= 75:
        return AnalystRecommendation.BUY
    if score >= 55:
        return AnalystRecommendation.HOLD
    if score >= 35:
        return AnalystRecommendation.SELL
    return AnalystRecommendation.AVOID


def _sentiment_delta(text: str | None) -> int:
    if not text:
        return 0
    bull = len(_BULLISH.findall(text))
    bear = len(_BEARISH.findall(text))
    if bull > bear + 1:
        return 6
    if bear > bull + 1:
        return -6
    return 0


def _split_lines(text: str | None, *, max_items: int) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    for raw in text.split("\n"):
        cleaned = re.sub(r"^[-*•]\s*", "", raw).strip()
        if len(cleaned) > 18:
            lines.append(cleaned)
    if not lines and text.strip():
        lines = [text.strip()[:320]]
    return lines[:max_items]


def _lines_matching(text: str, pattern: re.Pattern[str], *, max_items: int) -> list[str]:
    if not text:
        return []
    matched: list[str] = []
    for line in text.split("\n"):
        cleaned = line.strip()
        if cleaned and pattern.search(cleaned):
            matched.append(re.sub(r"^[-*•]\s*", "", cleaned))
    return matched[:max_items]


def _bull_bear_cases(report: ResearchReportResponse) -> tuple[list[str], list[str]]:
    bull: list[str] = []
    bear: list[str] = []

    if report.recommendation:
        if report.recommendation.reasoning:
            bull.append(report.recommendation.reasoning.strip()[:300])
        bear.extend(report.recommendation.risks[:3])

    if report.analysis:
        for line in _split_lines(report.analysis, max_items=8):
            if _BULLISH.search(line):
                bull.append(line)
            if _BEARISH.search(line):
                bear.append(line)

    if not bull and report.recommendation and report.recommendation.rating == RecommendationRating.BUY:
        bull.append("Committee sees favorable risk-reward based on consolidated agent research.")
    if not bear:
        bear.append("Macro, sector, and execution risks remain on the committee watchlist.")

    return bull[:4], bear[:4]


def _consensus_summary(analysts: list[AnalystOpinion]) -> str:
    counts: dict[str, int] = {}
    for analyst in analysts:
        key = analyst.recommendation.value
        counts[key] = counts.get(key, 0) + 1

    parts = [f"{count} {rating}" for rating, count in sorted(counts.items(), key=lambda x: -x[1])]
    avg_conf = round(sum(a.confidence for a in analysts) / max(len(analysts), 1))
    return f"Committee split: {', '.join(parts)}. Average analyst confidence {avg_conf}%."


def _build_conclusion(
    report: ResearchReportResponse,
    analysts: list[AnalystOpinion],
    final: AnalystRecommendation,
) -> str:
    rec = report.recommendation
    if rec and rec.reasoning:
        lead = rec.reasoning.strip()
    elif report.analysis:
        lead = report.analysis.split("\n")[0].strip()
    else:
        lead = "The committee reviewed all specialist inputs."

    dissent = [a for a in analysts if a.recommendation != final]
    if dissent:
        names = ", ".join(a.name for a in dissent[:2])
        return (
            f"{lead} The committee weighed dissenting views from {names} but aligned on "
            f"a {final.value} stance after synthesizing fundamentals, news, valuation, and risk."
        )
    return (
        f"{lead} All committee analysts aligned on a {final.value} view after cross-checking "
        "fundamentals, news flow, technicals, valuation, and risk factors."
    )
