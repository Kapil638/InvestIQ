"""Pydantic models for the full multi-agent research report."""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.agent_outputs import AnalysisOutput, RiskOutput
from app.schemas.financial import FinancialResearchResponse
from app.schemas.investment_committee import InvestmentCommittee
from app.schemas.news import NewsResearchResponse


class RecommendationRating(str, Enum):
    BUY = "Buy"
    HOLD = "Hold"
    AVOID = "Avoid"
    WATCHLIST = "Watchlist"


class GuardrailIssue(BaseModel):
    code: str
    message: str
    severity: str = "warning"  # warning | error


class GuardrailResult(BaseModel):
    passed: bool
    issues: list[GuardrailIssue] = Field(default_factory=list)
    retry_count: int = 0
    blocked_reason: str | None = None


class InvestmentRecommendation(BaseModel):
    rating: RecommendationRating
    confidence_score: float = Field(
        ge=0,
        le=100,
        description="Deterministic committee confidence – not parsed from LLM text.",
    )
    reasoning: str
    risks: list[str] = Field(default_factory=list)
    target_price_range: str | None = None
    investment_horizon: str | None = None
    portfolio_allocation_suggestion: str | None = None
    llm_suggested_confidence: float | None = Field(
        default=None,
        description="Optional LLM-parsed confidence for audit only; not used as source of truth.",
    )


class PipelineStageTrace(BaseModel):
    stage: str
    status: str  # running | completed | failed | skipped
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    detail: str | None = None
    cache_hit: bool = False
    tokens: int | None = None
    error: str | None = None


class ScoreBreakdown(BaseModel):
    financial_quality_score: int = Field(ge=0, le=100)
    valuation_score: int = Field(ge=0, le=100)
    growth_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    news_score: int = Field(ge=0, le=100)
    data_quality_score: int = Field(ge=0, le=100)


class StructuredRiskAssessment(BaseModel):
    risks: list[str] = Field(default_factory=list)
    source: str = "analysis"
    risk_count: int = 0


class ResearchReportResponse(BaseModel):
    """Full pipeline output – Agents 1–4 plus guardrails."""

    id: str | None = None
    ticker: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    financial_data: FinancialResearchResponse | None = None
    news_data: NewsResearchResponse | None = None
    financial_data_summary: str | None = None
    news_research_summary: str | None = None
    analysis: str | None = None
    analysis_output: AnalysisOutput | None = None
    structured_risks: StructuredRiskAssessment | None = None
    risk_output: RiskOutput | None = None
    guardrails: GuardrailResult | None = None
    risk_guardrails: GuardrailResult | None = None
    recommendation_guardrails: GuardrailResult | None = None
    recommendation: InvestmentRecommendation | None = None
    raw_recommendation: str | None = None
    investment_committee: InvestmentCommittee | None = None
    pipeline_trace: list[PipelineStageTrace] = Field(default_factory=list)
    confidence_score: int | None = Field(
        default=None, ge=0, le=100, description="Deterministic committee confidence."
    )
    score_breakdown: ScoreBreakdown | None = None
    scoring_version: str | None = None
    data_snapshot_hash: str | None = None
    confidence_change_reason: str | None = None
    regenerated_from_same_data: bool = False
    model_used: str | None = None
