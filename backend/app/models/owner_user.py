"""Domain models for the single-owner authentication gate."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OwnerUser(BaseModel):
    id: str
    google_sub: str
    email: str
    display_name: str | None = None
    picture_url: str | None = None
    created_at: datetime
    last_login_at: datetime | None = None


class WebAuthnCredential(BaseModel):
    id: str
    owner_id: str
    credential_id: str
    public_key: str
    sign_count: int = 0
    transports: list[str] = Field(default_factory=list)
    device_label: str | None = None
    created_at: datetime
    last_used_at: datetime | None = None
