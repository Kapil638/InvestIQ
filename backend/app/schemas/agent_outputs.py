"""Structured outputs from reasoning agents (Analysis, Risk, Recommendation)."""

from pydantic import BaseModel, Field


class AnalysisScores(BaseModel):
    growth: int = Field(ge=0, le=100)
    profitability: int = Field(ge=0, le=100)
    valuation: int = Field(ge=0, le=100)
    financial_health: int = Field(ge=0, le=100)
    management: int = Field(ge=0, le=100)
    sector_strength: int = Field(ge=0, le=100)
    macro: int = Field(ge=0, le=100)
    overall: int = Field(ge=0, le=100)


class AnalysisOutput(BaseModel):
    narrative: str
    scores: AnalysisScores
    scores_estimated: bool = False


class RiskScores(BaseModel):
    overall_risk: int = Field(ge=0, le=100, description="Higher = riskier")
    financial: int = Field(ge=0, le=100)
    governance: int = Field(ge=0, le=100)
    macro: int = Field(ge=0, le=100)
    business: int = Field(ge=0, le=100)
    valuation: int = Field(ge=0, le=100)
    regulatory: int = Field(ge=0, le=100)


class RiskOutput(BaseModel):
    narrative: str
    scores: RiskScores
    risks: list[str] = Field(default_factory=list)
    scores_estimated: bool = False
