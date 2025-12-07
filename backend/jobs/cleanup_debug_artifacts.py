from __future__ import annotations

import asyncio

from backend.config.debug_settings import DebugSettings
from backend.core.artifact_storage import PostgresArtifactStorage
from backend.core.logging import get_logger


logger = get_logger("rag.jobs.cleanup_debug_artifacts")


async def run_cleanup() -> None:
    """Cleanup job for debug artifacts based on retention settings.

    This job is intended to be run periodically (e.g., via cron or a
    scheduler) using::

        python -m backend.jobs.cleanup_debug_artifacts
    """

    settings = DebugSettings.from_env()
    storage = PostgresArtifactStorage()

    deleted = await storage.cleanup_old_artifacts(settings.retention_hours)
    logger.info(
        "debug_artifacts_cleanup_completed",
        extra={"deleted": deleted, "retention_hours": settings.retention_hours},
    )


if __name__ == "__main__":  # pragma: no cover - manual operational entrypoint
    asyncio.run(run_cleanup())
