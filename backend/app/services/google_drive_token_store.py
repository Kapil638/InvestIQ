"""Google Drive OAuth session store – persisted to disk so a refresh token
survives backend restarts (Google refresh tokens are long-lived, unlike Kite's
daily-expiring tokens, so pure in-memory storage would force re-auth on every
restart)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from app.utils.logging import get_logger

logger = get_logger(__name__)

_TOKEN_FILE = Path(__file__).resolve().parents[3] / "secrets" / "google-drive-oauth-token.json"


@dataclass
class GoogleDriveOAuthSession:
    access_token: str
    refresh_token: str
    token_uri: str
    client_id: str
    client_secret: str
    scopes: list[str]
    expiry: str  # ISO timestamp
    user_email: str | None = None


class GoogleDriveTokenStore:
    """Thread-safe singleton session store for Google Drive OAuth tokens."""

    def __init__(self, path: Path = _TOKEN_FILE) -> None:
        self._lock = Lock()
        self._path = path
        self._session: GoogleDriveOAuthSession | None = self._load()

    def _load(self) -> GoogleDriveOAuthSession | None:
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return GoogleDriveOAuthSession(**data)
        except Exception as exc:
            logger.warning("Failed to load Google Drive OAuth token from disk: %s", exc)
            return None

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._session is None:
                if self._path.exists():
                    self._path.unlink()
                return
            self._path.write_text(json.dumps(asdict(self._session)), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to persist Google Drive OAuth token to disk: %s", exc)

    def set_session(self, session: GoogleDriveOAuthSession) -> None:
        with self._lock:
            self._session = session
            self._persist()

    def get_session(self) -> GoogleDriveOAuthSession | None:
        with self._lock:
            return self._session

    def update_access_token(self, access_token: str, expiry: datetime) -> None:
        """Called after an automatic token refresh so the new access token survives restarts.

        google-auth's Credentials.expiry is a naive datetime already in UTC (not
        local time), so a bare tzinfo attach is correct here — astimezone() would
        incorrectly reinterpret it as local time on non-UTC machines.
        """
        with self._lock:
            if self._session is None:
                return
            self._session.access_token = access_token
            aware_expiry = expiry if expiry.tzinfo else expiry.replace(tzinfo=UTC)
            self._session.expiry = aware_expiry.isoformat()
            self._persist()

    def clear(self) -> None:
        with self._lock:
            self._session = None
            self._persist()

    def is_authenticated(self) -> bool:
        return self.get_session() is not None


# Process-wide store – one active Google Drive OAuth session per backend instance (MVP).
_token_store = GoogleDriveTokenStore()


def get_google_drive_token_store() -> GoogleDriveTokenStore:
    return _token_store
