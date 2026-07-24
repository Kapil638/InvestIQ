"""Map domain exceptions to HTTP responses."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.error_mapping import map_exception_to_response
from app.utils.exceptions import (
    ConfigurationError,
    ExternalServiceError,
    GoogleDriveNotConnectedError,
    GoogleDriveServiceError,
    GoogleSignInError,
    GrowwNotEnabledError,
    GrowwServiceError,
    InvestIQError,
    KiteAuthError,
    KiteBlockedToolError,
    KiteNotEnabledError,
    KiteServiceError,
    OwnerNotAllowedError,
    ReportNotFoundError,
    SessionRequiredError,
    TickerNotFoundError,
    WebAuthnError,
)

logger = logging.getLogger(__name__)


def _error_payload(detail: str, error_type: str, status: int | None = None) -> dict[str, str | int]:
    payload: dict[str, str | int] = {"detail": detail, "type": error_type}
    if status is not None:
        payload["status"] = status
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(
        _request: Request, exc: ConfigurationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=_error_payload(str(exc), type(exc).__name__, 503),
        )

    @app.exception_handler(TickerNotFoundError)
    async def ticker_not_found_handler(
        _request: Request, exc: TickerNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=_error_payload(str(exc), type(exc).__name__, 404),
        )

    @app.exception_handler(ReportNotFoundError)
    async def report_not_found_handler(
        _request: Request, exc: ReportNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=_error_payload(str(exc), type(exc).__name__, 404),
        )

    @app.exception_handler(KiteAuthError)
    async def kite_auth_error_handler(
        _request: Request, exc: KiteAuthError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=_error_payload(str(exc), type(exc).__name__, 401),
        )

    @app.exception_handler(KiteNotEnabledError)
    async def kite_not_enabled_handler(
        _request: Request, exc: KiteNotEnabledError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=_error_payload(str(exc), type(exc).__name__, 503),
        )

    @app.exception_handler(KiteBlockedToolError)
    async def kite_blocked_tool_handler(
        _request: Request, exc: KiteBlockedToolError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=_error_payload(str(exc), type(exc).__name__, 403),
        )

    @app.exception_handler(KiteServiceError)
    async def kite_service_error_handler(
        _request: Request, exc: KiteServiceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=_error_payload(str(exc), type(exc).__name__, 502),
        )

    @app.exception_handler(GrowwNotEnabledError)
    async def groww_not_enabled_handler(
        _request: Request, exc: GrowwNotEnabledError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=_error_payload(str(exc), type(exc).__name__, 503),
        )

    @app.exception_handler(GrowwServiceError)
    async def groww_service_error_handler(
        _request: Request, exc: GrowwServiceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=_error_payload(str(exc), type(exc).__name__, 502),
        )

    @app.exception_handler(GoogleDriveNotConnectedError)
    async def google_drive_not_connected_handler(
        _request: Request, exc: GoogleDriveNotConnectedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=_error_payload(str(exc), type(exc).__name__, 503),
        )

    @app.exception_handler(GoogleDriveServiceError)
    async def google_drive_service_error_handler(
        _request: Request, exc: GoogleDriveServiceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=_error_payload(str(exc), type(exc).__name__, 502),
        )

    @app.exception_handler(SessionRequiredError)
    async def session_required_handler(
        _request: Request, exc: SessionRequiredError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=_error_payload(str(exc), type(exc).__name__, 401),
        )

    @app.exception_handler(GoogleSignInError)
    async def google_signin_error_handler(
        _request: Request, exc: GoogleSignInError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=_error_payload(str(exc), type(exc).__name__, 401),
        )

    @app.exception_handler(OwnerNotAllowedError)
    async def owner_not_allowed_handler(
        _request: Request, exc: OwnerNotAllowedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=_error_payload(str(exc), type(exc).__name__, 403),
        )

    @app.exception_handler(WebAuthnError)
    async def webauthn_error_handler(_request: Request, exc: WebAuthnError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=_error_payload(str(exc), type(exc).__name__, 400),
        )

    @app.exception_handler(ExternalServiceError)
    async def external_service_error_handler(
        _request: Request, exc: ExternalServiceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=_error_payload(str(exc), type(exc).__name__, 502),
        )

    @app.exception_handler(InvestIQError)
    async def investiq_error_handler(_request: Request, exc: InvestIQError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_error_payload(str(exc), type(exc).__name__, 500),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        mapped = map_exception_to_response(exc)
        logger.exception(
            "Unhandled error on %s %s [%s]: %s",
            request.method,
            request.url.path,
            mapped.error_type,
            mapped.detail,
        )
        return JSONResponse(
            status_code=mapped.status_code,
            content=_error_payload(mapped.detail, mapped.error_type, mapped.status_code),
        )
