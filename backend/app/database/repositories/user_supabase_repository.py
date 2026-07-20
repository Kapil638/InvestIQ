"""Supabase repository for owner users and WebAuthn credentials."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.models.owner_user import OwnerUser, WebAuthnCredential
from app.utils.exceptions import ExternalServiceError
from app.utils.logging import get_logger

logger = get_logger(__name__)

OWNERS_TABLE = "app_users"
CREDENTIALS_TABLE = "webauthn_credentials"


def _format_supabase_error(exc: Exception) -> str:
    """Extract a readable message from Supabase/postgrest API errors."""
    current: BaseException | None = exc
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))

        message = getattr(current, "message", None)
        if isinstance(message, dict) and message.get("message"):
            return str(message["message"])
        if isinstance(message, str) and message.strip():
            return message.strip()

        text = str(current).strip()
        has_nested = bool(current.__cause__ or current.__context__)
        if text and text != type(current).__name__ and not (current is exc and has_nested):
            return text

        current = current.__cause__ or current.__context__

    return str(exc)


class SupabaseUserRepository:
    """Persists owner users and WebAuthn credentials to Supabase via PostgREST."""

    def __init__(self, url: str, key: str) -> None:
        self._url = url
        self._key = key
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from supabase import create_client
            except ImportError as exc:
                raise ImportError(
                    "supabase is required for PostgreSQL storage. "
                    "Install with: pip install supabase"
                ) from exc
            self._client = create_client(self._url, self._key)
        return self._client

    async def get_or_create_owner(
        self,
        *,
        google_sub: str,
        email: str,
        display_name: str | None,
        picture_url: str | None,
    ) -> OwnerUser:
        def _fetch_existing() -> dict | None:
            response = (
                self._get_client()
                .table(OWNERS_TABLE)
                .select("*")
                .eq("google_sub", google_sub)
                .limit(1)
                .execute()
            )
            data = response.data or []
            return data[0] if data else None

        try:
            existing = await asyncio.to_thread(_fetch_existing)
        except Exception as exc:
            detail = _format_supabase_error(exc)
            logger.error("Supabase owner lookup failed: %s", detail)
            raise ExternalServiceError(f"Failed to look up owner user: {detail}") from exc

        if existing:
            return _owner_from_row(existing)

        owner_id = str(uuid4())
        row = {
            "id": owner_id,
            "google_sub": google_sub,
            "email": email,
            "display_name": display_name,
            "picture_url": picture_url,
            "created_at": datetime.now(UTC).isoformat(),
        }

        def _insert() -> None:
            response = self._get_client().table(OWNERS_TABLE).insert(row).execute()
            if getattr(response, "error", None):
                raise ExternalServiceError(str(response.error))

        try:
            await asyncio.to_thread(_insert)
        except ExternalServiceError:
            raise
        except Exception as exc:
            detail = _format_supabase_error(exc)
            logger.error("Supabase owner insert failed: %s", detail)
            raise ExternalServiceError(f"Failed to create owner user: {detail}") from exc

        return _owner_from_row(row)

    async def get_owner_by_id(self, owner_id: str) -> OwnerUser | None:
        def _fetch() -> dict | None:
            response = (
                self._get_client()
                .table(OWNERS_TABLE)
                .select("*")
                .eq("id", owner_id)
                .limit(1)
                .execute()
            )
            data = response.data or []
            return data[0] if data else None

        row = await asyncio.to_thread(_fetch)
        return _owner_from_row(row) if row else None

    async def touch_last_login(self, owner_id: str) -> None:
        def _update() -> None:
            self._get_client().table(OWNERS_TABLE).update(
                {"last_login_at": datetime.now(UTC).isoformat()}
            ).eq("id", owner_id).execute()

        try:
            await asyncio.to_thread(_update)
        except Exception as exc:
            logger.warning("Failed to update owner last_login_at: %s", _format_supabase_error(exc))

    async def add_credential(
        self,
        *,
        owner_id: str,
        credential_id: str,
        public_key: str,
        sign_count: int,
        transports: list[str],
        device_label: str | None,
    ) -> WebAuthnCredential:
        row = {
            "id": str(uuid4()),
            "owner_id": owner_id,
            "credential_id": credential_id,
            "public_key": public_key,
            "sign_count": sign_count,
            "transports": ",".join(transports) if transports else None,
            "device_label": device_label,
            "created_at": datetime.now(UTC).isoformat(),
        }

        def _insert() -> None:
            response = self._get_client().table(CREDENTIALS_TABLE).insert(row).execute()
            if getattr(response, "error", None):
                raise ExternalServiceError(str(response.error))

        try:
            await asyncio.to_thread(_insert)
        except ExternalServiceError:
            raise
        except Exception as exc:
            detail = _format_supabase_error(exc)
            logger.error("Supabase credential insert failed: %s", detail)
            raise ExternalServiceError(f"Failed to store WebAuthn credential: {detail}") from exc

        return _credential_from_row(row)

    async def get_credential(self, credential_id: str) -> WebAuthnCredential | None:
        def _fetch() -> dict | None:
            response = (
                self._get_client()
                .table(CREDENTIALS_TABLE)
                .select("*")
                .eq("credential_id", credential_id)
                .limit(1)
                .execute()
            )
            data = response.data or []
            return data[0] if data else None

        row = await asyncio.to_thread(_fetch)
        return _credential_from_row(row) if row else None

    async def list_credentials(self, owner_id: str | None = None) -> list[WebAuthnCredential]:
        def _fetch() -> list[dict]:
            query = self._get_client().table(CREDENTIALS_TABLE).select("*")
            if owner_id is not None:
                query = query.eq("owner_id", owner_id)
            response = query.execute()
            return response.data or []

        rows = await asyncio.to_thread(_fetch)
        return [_credential_from_row(row) for row in rows]

    async def update_sign_count(self, credential_id: str, sign_count: int) -> None:
        def _update() -> None:
            self._get_client().table(CREDENTIALS_TABLE).update(
                {"sign_count": sign_count, "last_used_at": datetime.now(UTC).isoformat()}
            ).eq("credential_id", credential_id).execute()

        try:
            await asyncio.to_thread(_update)
        except Exception as exc:
            logger.warning("Failed to update credential sign_count: %s", _format_supabase_error(exc))


def _owner_from_row(row: dict[str, Any]) -> OwnerUser:
    return OwnerUser(
        id=row["id"],
        google_sub=row["google_sub"],
        email=row["email"],
        display_name=row.get("display_name"),
        picture_url=row.get("picture_url"),
        created_at=row["created_at"],
        last_login_at=row.get("last_login_at"),
    )


def _credential_from_row(row: dict[str, Any]) -> WebAuthnCredential:
    transports_raw = row.get("transports")
    transports = transports_raw.split(",") if transports_raw else []
    return WebAuthnCredential(
        id=row["id"],
        owner_id=row["owner_id"],
        credential_id=row["credential_id"],
        public_key=row["public_key"],
        sign_count=row.get("sign_count", 0),
        transports=transports,
        device_label=row.get("device_label"),
        created_at=row["created_at"],
        last_used_at=row.get("last_used_at"),
    )
