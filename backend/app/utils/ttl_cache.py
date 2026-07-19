"""Lightweight in-process TTL cache – respects CACHE_ENABLED from settings."""

from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

from app.core.config import Settings, get_settings

T = TypeVar("T")

# Namespace TTLs (seconds) – used when CACHE_ENABLED=true
NAMESPACE_TTL: dict[str, int] = {
    "search": 600,
    "financial": 300,
    "history": 300,
    "status": 60,
    "report": 60,
    "holdings": 60,
    "chat_context": 300,
    "advisor": 300,
}

_store: dict[str, tuple[float, Any]] = {}


def _enabled() -> bool:
    return get_settings().cache_enabled


def _ttl(namespace: str) -> int:
    settings = get_settings()
    return NAMESPACE_TTL.get(namespace, settings.cache_ttl_seconds)


def cache_key(namespace: str, *parts: str) -> str:
    return f"{namespace}:" + ":".join(parts)


def get(namespace: str, key: str) -> Any | None:
    if not _enabled():
        return None
    full_key = cache_key(namespace, key)
    entry = _store.get(full_key)
    if not entry:
        return None
    expires_at, value = entry
    if time.monotonic() >= expires_at:
        _store.pop(full_key, None)
        return None
    return value


def set(namespace: str, key: str, value: Any) -> None:
    if not _enabled():
        return
    full_key = cache_key(namespace, key)
    _store[full_key] = (time.monotonic() + _ttl(namespace), value)


def get_or_set(namespace: str, key: str, factory: Callable[[], T]) -> T:
    cached = get(namespace, key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    value = factory()
    set(namespace, key, value)
    return value


async def get_or_set_async(
    namespace: str,
    key: str,
    factory: Callable[[], Any],
) -> Any:
    cached = get(namespace, key)
    if cached is not None:
        return cached
    value = await factory()
    set(namespace, key, value)
    return value


def delete(namespace: str, key: str) -> None:
    _store.pop(cache_key(namespace, key), None)


def clear_namespace(namespace: str) -> None:
    prefix = f"{namespace}:"
    for key in list(_store):
        if key.startswith(prefix):
            _store.pop(key, None)


def clear_all() -> None:
    _store.clear()


def configure_from_settings(settings: Settings) -> None:
    """No-op hook for tests – TTLs read from NAMESPACE_TTL + settings on each access."""
    _ = settings
