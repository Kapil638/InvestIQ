"""Pydantic models for the owner authentication gate."""

from typing import Any

from pydantic import BaseModel


class GoogleSignInRequest(BaseModel):
    id_token: str


class AuthStatusResponse(BaseModel):
    authenticated: bool
    owner_auth_configured: bool
    email: str | None = None
    display_name: str | None = None
    picture_url: str | None = None
    has_passkey: bool = False


class WebAuthnRegisterVerifyRequest(BaseModel):
    credential: dict[str, Any]
    device_label: str | None = None


class WebAuthnAuthenticateVerifyRequest(BaseModel):
    credential: dict[str, Any]
