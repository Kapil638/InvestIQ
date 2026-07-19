"""Company search API schemas."""

from pydantic import BaseModel, Field


class CompanySearchResult(BaseModel):
    symbol: str
    exchange: str
    company_name: str
    sector: str | None = None
    source: str


class CompanySearchResponse(BaseModel):
    results: list[CompanySearchResult] = Field(default_factory=list)
    source: str = "static"
    fallback: bool = False
