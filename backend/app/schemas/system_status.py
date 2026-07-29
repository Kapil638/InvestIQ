from pydantic import BaseModel


class DatabaseStatusResponse(BaseModel):
    """Live Supabase connectivity check - kept separate from /health so a
    transient DB hiccup never influences Render's own restart decisions,
    which are driven by the unauthenticated /health probe."""

    connected: bool
    message: str
    latency_ms: float | None = None
