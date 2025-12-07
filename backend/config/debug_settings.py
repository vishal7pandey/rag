from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class DebugSettings:
    """Configuration for debug artifact logging (Story 016).

    When ``enabled`` is False, artifact logging should have effectively zero
    overhead beyond a single boolean check at call sites.
    """

    enabled: bool = False
    store_raw_artifacts: bool = True
    retention_hours: int = 24
    max_artifact_size_bytes: int = 100_000
    include_chunk_content: bool = True
    include_prompt_details: bool = True
    include_llm_raw_output: bool = True

    @classmethod
    def from_env(cls) -> "DebugSettings":
        """Load debug settings from environment variables.

        Environment variables:
        - DEBUG_RAG: "true"/"false" (case-insensitive)
        - DEBUG_STORE_ARTIFACTS: "true"/"false"
        - DEBUG_RETENTION_HOURS: integer hours
        - DEBUG_MAX_SIZE: integer bytes
        """

        def _as_bool(name: str, default: str) -> bool:
            return os.getenv(name, default).lower() == "true"

        enabled = _as_bool("DEBUG_RAG", "false")
        store_raw = _as_bool("DEBUG_STORE_ARTIFACTS", "true")
        retention = int(os.getenv("DEBUG_RETENTION_HOURS", "24"))
        max_size = int(os.getenv("DEBUG_MAX_SIZE", "100000"))

        return cls(
            enabled=enabled,
            store_raw_artifacts=store_raw,
            retention_hours=retention,
            max_artifact_size_bytes=max_size,
        )
