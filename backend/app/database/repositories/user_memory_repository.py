"""In-memory owner-user/WebAuthn-credential repository for development and tests.

Caveat: without Supabase configured, passkey registrations are lost on every
backend restart (e.g. every `uvicorn --reload` reload during local dev). Fine
as a documented tradeoff for local dev; a JSON-file persistence fallback (same
pattern as GoogleDriveTokenStore) is a possible later follow-up, not needed now.
"""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from app.models.owner_user import OwnerUser, WebAuthnCredential


class InMemoryUserRepository:
    """Thread-safe in-process storage – no external database required."""

    def __init__(self) -> None:
        self._owners: dict[str, OwnerUser] = {}
        self._owners_by_sub: dict[str, str] = {}
        self._credentials: dict[str, WebAuthnCredential] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_owner(
        self,
        *,
        google_sub: str,
        email: str,
        display_name: str | None,
        picture_url: str | None,
    ) -> OwnerUser:
        async with self._lock:
            owner_id = self._owners_by_sub.get(google_sub)
            if owner_id is not None:
                return self._owners[owner_id]

            new_id = str(uuid4())
            owner = OwnerUser(
                id=new_id,
                google_sub=google_sub,
                email=email,
                display_name=display_name,
                picture_url=picture_url,
                created_at=datetime.now(UTC),
            )
            self._owners[new_id] = owner
            self._owners_by_sub[google_sub] = new_id
            return owner

    async def get_owner_by_id(self, owner_id: str) -> OwnerUser | None:
        async with self._lock:
            return self._owners.get(owner_id)

    async def touch_last_login(self, owner_id: str) -> None:
        async with self._lock:
            owner = self._owners.get(owner_id)
            if owner is not None:
                self._owners[owner_id] = owner.model_copy(
                    update={"last_login_at": datetime.now(UTC)}
                )

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
        credential = WebAuthnCredential(
            id=str(uuid4()),
            owner_id=owner_id,
            credential_id=credential_id,
            public_key=public_key,
            sign_count=sign_count,
            transports=transports,
            device_label=device_label,
            created_at=datetime.now(UTC),
        )
        async with self._lock:
            self._credentials[credential_id] = credential
        return credential

    async def get_credential(self, credential_id: str) -> WebAuthnCredential | None:
        async with self._lock:
            return self._credentials.get(credential_id)

    async def list_credentials(self, owner_id: str | None = None) -> list[WebAuthnCredential]:
        async with self._lock:
            items = list(self._credentials.values())
        if owner_id is not None:
            items = [c for c in items if c.owner_id == owner_id]
        return items

    async def update_sign_count(self, credential_id: str, sign_count: int) -> None:
        async with self._lock:
            credential = self._credentials.get(credential_id)
            if credential is not None:
                self._credentials[credential_id] = credential.model_copy(
                    update={"sign_count": sign_count, "last_used_at": datetime.now(UTC)}
                )

    def clear(self) -> None:
        self._owners.clear()
        self._owners_by_sub.clear()
        self._credentials.clear()
