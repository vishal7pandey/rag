from __future__ import annotations

import os
from unittest.mock import patch

from backend.config.debug_settings import DebugSettings


def test_debug_settings_disabled_by_default() -> None:
    """Debug logging is disabled when DEBUG_RAG is not set."""

    with patch.dict(os.environ, {}, clear=True):
        settings = DebugSettings.from_env()
        assert settings.enabled is False


def test_debug_settings_enabled_from_env() -> None:
    """DEBUG_RAG=true enables debug logging."""

    with patch.dict(os.environ, {"DEBUG_RAG": "true"}, clear=True):
        settings = DebugSettings.from_env()
        assert settings.enabled is True


def test_debug_settings_retention_from_env() -> None:
    """Retention hours are configurable via DEBUG_RETENTION_HOURS."""

    with patch.dict(os.environ, {"DEBUG_RETENTION_HOURS": "48"}, clear=True):
        settings = DebugSettings.from_env()
        assert settings.retention_hours == 48


def test_debug_settings_max_artifact_size_from_env() -> None:
    """Max artifact size is configurable via DEBUG_MAX_SIZE."""

    with patch.dict(os.environ, {"DEBUG_MAX_SIZE": "12345"}, clear=True):
        settings = DebugSettings.from_env()
        assert settings.max_artifact_size_bytes == 12345
