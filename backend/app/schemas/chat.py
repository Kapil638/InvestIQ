"""Schemas for report follow-up chat."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ReportChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list)


class ReportChatResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    report_id: str
