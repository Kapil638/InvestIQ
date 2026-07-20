"""Owner session issuance and verification for the single-owner auth gate.

Session = a stateless signed cookie (itsdangerous), not a JWT — this is exactly
"signed value with an expiry," so itsdangerous avoids the unneeded algorithm/
audience/issuer surface a JWT library would bring for no benefit here.

Known accepted limitation: logout only clears the client-side cookie. The
signed token itself isn't server-revocable before it naturally expires
(SESSION_MAX_AGE_DAYS). Fine for a personal single-device tool with a modest
default; would need a server-side revocation list to close that gap.
"""

from __future__ import annotations

import secrets as secrets_module
from dataclasses import dataclass

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import Settings
from app.database.repositories.base import UserRepository
from app.models.owner_user import OwnerUser
from app.services.google_signin_service import verify_google_id_token
from app.utils.exceptions import OwnerNotAllowedError
from app.utils.logging import get_logger

logger = get_logger(__name__)

SESSION_COOKIE_NAME = "investiq_session"
CHALLENGE_COOKIE_NAME = "investiq_webauthn_challenge"
_SESSION_SALT = "session"
_CHALLENGE_SALT = "webauthn-challenge"
_CHALLENGE_MAX_AGE_SECONDS = 300  # 5 minutes — only needs to survive one round trip

# Ephemeral fallback so the app still runs (with sessions invalidated on every
# restart) if SESSION_SECRET_KEY isn't set. A warning is logged once at startup
# (see config.log_startup_config) — this is not silent.
_EPHEMERAL_SECRET = secrets_module.token_urlsafe(32)


@dataclass(frozen=True)
class OwnerSessionData:
    owner_id: str
    email: str


class OwnerAuthService:
    def __init__(self, settings: Settings, user_repo: UserRepository) -> None:
        self._settings = settings
        self._user_repo = user_repo

    async def sign_in_with_google(self, id_token: str) -> tuple[OwnerUser, str]:
        identity = await verify_google_id_token(id_token, self._settings)

        if identity.email.lower() not in self._settings.allowed_owner_emails_list:
            raise OwnerNotAllowedError(f"{identity.email} is not an authorized InvestIQ account.")

        user = await self._user_repo.get_or_create_owner(
            google_sub=identity.sub,
            email=identity.email,
            display_name=identity.name,
            picture_url=identity.picture,
        )
        await self._user_repo.touch_last_login(user.id)

        return user, self.create_session_token(user.id, user.email)

    def create_session_token(self, owner_id: str, email: str) -> str:
        return self._serializer(_SESSION_SALT).dumps({"owner_id": owner_id, "email": email})

    def verify_session_token(self, token: str) -> OwnerSessionData | None:
        max_age = self._settings.session_max_age_days * 86400
        try:
            data = self._serializer(_SESSION_SALT).loads(token, max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None
        return OwnerSessionData(owner_id=data["owner_id"], email=data["email"])

    def create_challenge_token(self, challenge: bytes) -> str:
        return self._serializer(_CHALLENGE_SALT).dumps({"challenge": challenge.hex()})

    def verify_challenge_token(self, token: str) -> bytes | None:
        try:
            data = self._serializer(_CHALLENGE_SALT).loads(
                token, max_age=_CHALLENGE_MAX_AGE_SECONDS
            )
        except (BadSignature, SignatureExpired):
            return None
        return bytes.fromhex(data["challenge"])

    def _serializer(self, salt: str) -> URLSafeTimedSerializer:
        secret = self._settings.session_secret_key or _EPHEMERAL_SECRET
        return URLSafeTimedSerializer(secret, salt=salt)
