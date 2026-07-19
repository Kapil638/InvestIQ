"""Google Drive OAuth endpoints (login, callback, status, logout)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.api.dependencies import get_google_drive_auth_service
from app.schemas.google_drive import GoogleDriveStatusResponse
from app.services.google_drive_auth_service import GoogleDriveAuthService
from app.utils.exceptions import GoogleDriveAuthError
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["google-drive"])


@router.get("/google-drive/status", response_model=GoogleDriveStatusResponse)
async def google_drive_status(
    auth_service: GoogleDriveAuthService = Depends(get_google_drive_auth_service),
) -> GoogleDriveStatusResponse:
    """Return Google Drive OAuth status (always 200 – check `authenticated`/`connected`)."""
    enabled = auth_service.is_enabled
    configured = auth_service.is_configured()
    authenticated = auth_service.is_authenticated()

    if not enabled:
        message = "Google Drive is not enabled."
    elif not configured:
        message = "Google Drive OAuth client is not configured."
    elif not authenticated:
        message = "Google Drive is not connected. Connect your account to save reports."
    else:
        email = auth_service.get_user_email()
        message = f"Connected to Google Drive as {email}." if email else "Connected to Google Drive."

    return GoogleDriveStatusResponse(
        enabled=enabled,
        oauth_configured=configured,
        authenticated=authenticated,
        connected=enabled and configured and authenticated,
        user_email=auth_service.get_user_email(),
        message=message,
    )


@router.get("/google-drive/login")
async def google_drive_login(
    auth_service: GoogleDriveAuthService = Depends(get_google_drive_auth_service),
) -> RedirectResponse:
    """Redirect user to Google's OAuth consent screen (step 1)."""
    try:
        login_url = auth_service.get_login_url()
    except GoogleDriveAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return RedirectResponse(url=login_url, status_code=302)


@router.get("/google-drive/callback")
async def google_drive_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    auth_service: GoogleDriveAuthService = Depends(get_google_drive_auth_service),
) -> RedirectResponse:
    """OAuth callback – exchange code for tokens (server-side only)."""
    try:
        await auth_service.handle_callback(code, state, error)
        return RedirectResponse(
            url=auth_service.get_frontend_redirect_url(success=True),
            status_code=302,
        )
    except GoogleDriveAuthError as exc:
        logger.warning("Google Drive OAuth callback failed: %s", exc)
        return RedirectResponse(
            url=auth_service.get_frontend_redirect_url(success=False),
            status_code=302,
        )


@router.post("/google-drive/logout")
async def google_drive_logout(
    auth_service: GoogleDriveAuthService = Depends(get_google_drive_auth_service),
) -> dict[str, bool]:
    """Disconnect the stored Google Drive OAuth session."""
    auth_service.logout()
    return {"success": True}
