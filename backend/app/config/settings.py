"""Backward-compatible re-exports. Prefer `app.core.config`."""

from app.core.config import Settings, get_settings, log_startup_config, settings

__all__ = ["Settings", "get_settings", "log_startup_config", "settings"]
