from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Standard health-check payload."""

    status: str = Field(..., examples=["ok"])
    app_name: str
    version: str
    environment: str
    llm_provider: str | None = None
    llm_model: str | None = None
