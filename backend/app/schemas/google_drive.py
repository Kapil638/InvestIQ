"""Pydantic models for Google Drive OAuth status."""

from pydantic import BaseModel


class GoogleDriveStatusResponse(BaseModel):
    enabled: bool
    oauth_configured: bool
    authenticated: bool = False
    connected: bool = False
    user_email: str | None = None
    message: str
