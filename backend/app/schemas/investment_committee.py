"""Investment Committee – analyst personas and committee verdict models."""

from enum import Enum

from pydantic import BaseModel, Field


class AnalystRecommendation(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    AVOID = "AVOID"


class AnalystPersonaId(str, Enum):
    FUNDAMENTAL = "fundamental"
    NEWS = "news"
    TECHNICAL = "technical"
    VALUATION = "valuation"
    RISK = "risk"


class AnalystOpinion(BaseModel):
    """Single committee analyst view – extensible for future personas."""

    id: AnalystPersonaId
    name: str
    title: str
    recommendation: AnalystRecommendation
    confidence: int = Field(ge=0, le=100)
    supporting_points: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class CommitteeVerdict(BaseModel):
    final_recommendation: AnalystRecommendation
    overall_confidence: int = Field(ge=0, le=100)
    investment_horizon: str | None = None
    bull_case: list[str] = Field(default_factory=list)
    bear_case: list[str] = Field(default_factory=list)
    conclusion: str
    consensus_summary: str


class InvestmentCommittee(BaseModel):
    analysts: list[AnalystOpinion] = Field(default_factory=list)
    verdict: CommitteeVerdict
    sources_used: list[str] = Field(default_factory=list)
