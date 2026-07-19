"""In-memory Kite session store – replaceable with Supabase persistence later."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock


@dataclass
class KiteSession:
    access_token: str
    user_id: str
    user_name: str | None
    broker: str
    login_time: datetime
    public_token: str | None = None


class KiteTokenStore:
    """Thread-safe singleton session store for Zerodha OAuth tokens."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._session: KiteSession | None = None

    def set_session(self, session: KiteSession) -> None:
        with self._lock:
            self._session = session

    def get_session(self) -> KiteSession | None:
        with self._lock:
            return self._session

    def clear(self) -> None:
        with self._lock:
            self._session = None

    def is_authenticated(self) -> bool:
        return self.get_session() is not None


# Process-wide store – one active Zerodha session per backend instance (MVP).
_token_store = KiteTokenStore()


def get_kite_token_store() -> KiteTokenStore:
    return _token_store
