"""Pydantic models for targeted research Q&A."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ResearchAskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class ResearchAskResponse(BaseModel):
    ticker: str
    company_name: str
    question: str
    answer: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data_sources: list[str] = Field(default_factory=list)
