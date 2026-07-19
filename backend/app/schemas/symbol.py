"""Canonical resolved symbol from company master."""

from pydantic import BaseModel, Field


class ResolvedSymbol(BaseModel):
    """Single canonical instrument identity used across Search, Advisor, and Portfolio."""

    symbol: str = Field(description="Bare exchange ticker, e.g. INFY")
    company_name: str
    exchange: str = Field(default="NSE", description="NSE or BSE")
    isin: str = ""
    series: str = ""
    source: str = Field(default="nse", description="Data source slug, e.g. nse")
