"""Map exceptions to HTTP status codes and user-visible error messages."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class MappedError:
    status_code: int
    detail: str
    error_type: str


def _iter_exception_chain(exc: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        if current.__cause__ is not None:
            current = current.__cause__
        elif current.__context__ is not None:
            current = current.__context__
        else:
            break


def _google_genai_client_error(exc: BaseException) -> MappedError | None:
    try:
        from google.genai.errors import ClientError
    except ImportError:
        return None

    if not isinstance(exc, ClientError):
        return None

    status_code = int(getattr(exc, "status_code", None) or 500)
    message = _extract_google_error_message(exc)
    return MappedError(
        status_code=status_code,
        detail=message,
        error_type=type(exc).__name__,
    )


def _extract_google_error_message(exc: BaseException) -> str:
    response_json = getattr(exc, "response_json", None)
    if isinstance(response_json, dict):
        error = response_json.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])

    text = str(exc).strip()
    match = re.match(r"^\d+\s+[A-Z_]+\.\s*(.+)$", text, re.DOTALL)
    if match:
        payload = match.group(1).strip()
        dict_match = re.search(r"'message':\s*'([^']+)'", payload)
        if dict_match:
            return dict_match.group(1)
        if not payload.startswith("{"):
            return payload

    return text or type(exc).__name__


def _message_indicates_quota(message: str) -> bool:
    lowered = message.lower()
    return "resource_exhausted" in lowered or "quota exceeded" in lowered or (
        "quota" in lowered and "exceeded" in lowered
    )


def _message_indicates_auth_failure(message: str) -> bool:
    lowered = message.lower()
    return (
        "unauthenticated" in lowered
        or "invalid authentication" in lowered
        or "api key not valid" in lowered
        or "api_key_invalid" in lowered
    )


def map_exception_to_response(exc: Exception) -> MappedError:
    """Convert any exception into an HTTP-friendly error payload."""
    for linked in _iter_exception_chain(exc):
        mapped = _google_genai_client_error(linked)
        if mapped is not None:
            if mapped.status_code == 429 or _message_indicates_quota(mapped.detail):
                return MappedError(
                    status_code=429,
                    detail=mapped.detail,
                    error_type=mapped.error_type,
                )
            if mapped.status_code == 401 or _message_indicates_auth_failure(mapped.detail):
                return MappedError(
                    status_code=401,
                    detail=(
                        f"{mapped.detail} "
                        "Check OPENROUTER_API_KEY in backend/.env and restart the backend."
                    ),
                    error_type=mapped.error_type,
                )
            return mapped

        message = str(linked)
        lowered = message.lower()

        if isinstance(linked, ImportError) and "google-genai" in lowered:
            return MappedError(
                status_code=503,
                detail=(
                    'Google Gen AI provider is not installed. '
                    'Run: pip install "crewai[google-genai]"'
                ),
                error_type=type(linked).__name__,
            )

        if _message_indicates_quota(message):
            return MappedError(
                status_code=429,
                detail=_extract_google_error_message(linked)
                if "google.genai" in type(linked).__module__
                else message,
                error_type=type(linked).__name__,
            )

        if _message_indicates_auth_failure(message):
            return MappedError(
                status_code=401,
                detail=(
                    f"{_extract_google_error_message(linked)} "
                    "Check OPENROUTER_API_KEY in backend/.env and restart the backend."
                ),
                error_type=type(linked).__name__,
            )

    message = str(exc).strip() or "An unexpected error occurred."
    return MappedError(
        status_code=500,
        detail=message,
        error_type=type(exc).__name__,
    )
