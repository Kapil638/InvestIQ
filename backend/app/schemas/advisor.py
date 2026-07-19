"""Schemas for AI Investment Advisor recommendations."""

from __future__ import annotations

from pydantic import BaseModel, Field

ADVISOR_DISCLAIMER = (
    "Research output only. Not investment advice. No trades are executed."
)

THEME_MATCH_THRESHOLD = 60


class AdvisorPortfolioHolding(BaseModel):
    symbol: str
    company_name: str | None = None
    sector: str | None = None
    current_value: float | None = None


class AdvisorRecommendRequest(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=4000)
    portfolio_context: list[AdvisorPortfolioHolding] | None = None


class ThemeIntent(BaseModel):
    name: str
    keywords: list[str] = Field(default_factory=list)
    related_sectors: list[str] = Field(default_factory=list)
    inclusion_criteria: str = ""
    exclusion_criteria: str = ""


class InvestorProfile(BaseModel):
    """Explicit user-provided fields only — null/empty when not stated in prompt."""

    capital: str | None = None
    time_horizon: str | None = None
    risk_appetite: str | None = None
    preferences: list[str] = Field(default_factory=list)
    avoidances: list[str] = Field(default_factory=list)
    market_cap_preference: str | None = None
    dividend_growth_preference: str | None = None
    investment_style: str | None = None
    themes: list[ThemeIntent] = Field(default_factory=list)


class ProfileFieldDisplay(BaseModel):
    label: str
    value: str | None = None
    source: str = "missing"  # user | assumed | missing


class AdvisorRetrievalSummary(BaseModel):
    raw_candidates_count: int = 0
    validated_candidates_count: int = 0
    providers_used: list[str] = Field(default_factory=list)


class CompanyResearchAction(BaseModel):
    symbol: str
    company_name: str | None = None
    message: str


class StockRecommendation(BaseModel):
    rank: int = Field(..., ge=1, le=5)
    symbol: str
    company_name: str
    sector: str = "Not available"
    match_score: int = Field(..., ge=0, le=100)
    suggested_allocation_percent: float = Field(..., ge=0, le=100)
    why_it_fits: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    matched_themes: list[str] = Field(default_factory=list)
    theme_match_score: int = Field(0, ge=0, le=100)
    theme_match_reason: str = "Not available"
    key_evidence: list[str] = Field(default_factory=list)
    financial_quality_score: int | None = None
    valuation_score: int | None = None
    risk_score: int | None = None
    overall_match_score: int = Field(0, ge=0, le=100)


class SectorExposureItem(BaseModel):
    sector: str
    percent: float = Field(..., ge=0, le=100)


class PortfolioMix(BaseModel):
    large_cap_percent: float = Field(0, ge=0, le=100)
    mid_cap_percent: float = Field(0, ge=0, le=100)
    small_cap_percent: float = Field(0, ge=0, le=100)
    sector_exposure: list[SectorExposureItem] = Field(default_factory=list)
    risk_summary: str = "Not available"
    time_horizon_suitability: str = "Not available"


class AdvisorRecommendResponse(BaseModel):
    intent: str = "UNKNOWN"
    investor_profile: InvestorProfile
    profile_fields: list[ProfileFieldDisplay] = Field(default_factory=list)
    recommendations: list[StockRecommendation]
    portfolio_mix: PortfolioMix
    disclaimer: str = ADVISOR_DISCLAIMER
    warning: str | None = None
    assumptions_used: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    retrieval_summary: AdvisorRetrievalSummary = Field(default_factory=AdvisorRetrievalSummary)
    clarification_message: str | None = None
    company_research_action: CompanyResearchAction | None = None


class RawCandidate(BaseModel):
    symbol: str
    company_name: str
    exchange: str
    sector: str | None = None
    source: str


class CandidateValidation(BaseModel):
    symbol: str
    is_valid: bool = False
    matched_themes: list[str] = Field(default_factory=list)
    theme_match_score: int = Field(0, ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)
    reason: str = ""
    reject_reason: str | None = None
