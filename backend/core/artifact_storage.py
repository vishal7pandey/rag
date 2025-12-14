from __future__ import annotations

import json
from typing import Any, Dict, List, Protocol

from sqlalchemy import text

from backend.data_layer.postgres_client import PostgresClient


class ArtifactStorage(Protocol):
    """Abstract storage interface for debug artifacts (Story 016)."""

    async def store(
        self,
        trace_id: str,
        artifact_type: str,
        artifact_data: Dict[str, Any],
    ) -> None: ...

    async def get_by_trace_id(self, trace_id: str) -> List[Dict[str, Any]]: ...

    async def cleanup_old_artifacts(self, retention_hours: int) -> int: ...


class InMemoryArtifactStorage:
    """Simple in-memory artifact storage for development and tests.

    This avoids introducing a database dependency for Story 016 while still
    satisfying the requirement that artifacts be queryable by trace ID.
    """

    def __init__(self) -> None:
        # {trace_id: [artifact, ...]}
        self._artifacts: Dict[str, List[Dict[str, Any]]] = {}

    async def store(
        self,
        trace_id: str,
        artifact_type: str,
        artifact_data: Dict[str, Any],
    ) -> None:
        entry = {
            "type": artifact_type,
            "data": artifact_data,
        }
        self._artifacts.setdefault(trace_id, []).append(entry)

    async def get_by_trace_id(self, trace_id: str) -> List[Dict[str, Any]]:
        # Return a shallow copy to avoid accidental external mutation.
        return list(self._artifacts.get(trace_id, []))

    async def cleanup_old_artifacts(self, retention_hours: int) -> int:
        """No-op cleanup for in-memory storage.

        This implementation is primarily for development and tests; it does
        not enforce time-based retention and simply reports that no artifacts
        were deleted.
        """

        return 0


class PostgresArtifactStorage:
    """PostgreSQL-backed storage for debug artifacts (Story 016).

    Uses the existing PostgresClient and synchronous SQLAlchemy engine. The
    public methods are async for compatibility with ArtifactLogger but perform
    their work synchronously inside the event loop. This is acceptable for the
    low-volume, debug-only workload in Story 016.
    """

    def __init__(self, postgres_client: PostgresClient | None = None) -> None:
        self._postgres = postgres_client or PostgresClient()

    async def store(
        self,
        trace_id: str,
        artifact_type: str,
        artifact_data: Dict[str, Any],
    ) -> None:
        artifact_json = json.dumps(artifact_data)
        with self._postgres.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO debug_artifacts (
                        trace_id,
                        artifact_type,
                        artifact_data,
                        created_at
                    ) VALUES (:trace_id, :artifact_type, CAST(:artifact_data AS JSONB), NOW())
                    """
                ),
                {
                    "trace_id": trace_id,
                    "artifact_type": artifact_type,
                    "artifact_data": artifact_json,
                },
            )

    async def get_by_trace_id(self, trace_id: str) -> List[Dict[str, Any]]:
        with self._postgres.engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT artifact_type, artifact_data, created_at
                    FROM debug_artifacts
                    WHERE trace_id = :trace_id
                    ORDER BY created_at ASC
                    """
                ),
                {"trace_id": trace_id},
            )

            rows = result.fetchall()

        return [
            {
                "type": row.artifact_type,
                "data": row.artifact_data,
                "timestamp": row.created_at.isoformat()
                if getattr(row, "created_at", None) is not None
                else None,
            }
            for row in rows
        ]

    async def cleanup_old_artifacts(self, retention_hours: int) -> int:
        """Delete artifacts older than the given retention window."""

        if retention_hours <= 0:
            return 0

        hours = int(retention_hours)

        with self._postgres.engine.begin() as conn:
            result = conn.execute(
                text(
                    f"""
                    DELETE FROM debug_artifacts
                    WHERE created_at < NOW() - INTERVAL '{hours} hours'
                    """
                )
            )

        # SQLAlchemy 2.x returns a CursorResult; rowcount may be -1 for some
        # drivers, so guard against that and return a non-negative value.
        deleted = getattr(result, "rowcount", 0) or 0
        return max(deleted, 0)
