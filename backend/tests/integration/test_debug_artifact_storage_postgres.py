"""Integration tests for PostgresArtifactStorage and retention cleanup.

These tests follow the same pattern as other Postgres integration tests: they
require DATABASE_URL to be set and Postgres to be reachable. When that is not
true, the tests are skipped gracefully so that CI can run without a database.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from backend.core.artifact_storage import PostgresArtifactStorage
from backend.data_layer.postgres_client import PostgresClient


def _skip_reason() -> str | None:
    if not os.getenv("DATABASE_URL"):
        return "DATABASE_URL not set; debug_artifact_storage tests skipped"
    try:
        client = PostgresClient()
        if not client.test_connection():
            return "Postgres not reachable; debug_artifact_storage tests skipped"
    except Exception as exc:  # pragma: no cover - defensive
        return f"Postgres unavailable: {exc}"
    return None


@pytest.fixture(scope="module")
def postgres_client() -> PostgresClient:
    reason = _skip_reason()
    if reason is not None:
        pytest.skip(reason)
    return PostgresClient()


@pytest.mark.asyncio
async def test_cleanup_old_artifacts_deletes_older_rows(
    postgres_client: PostgresClient,
) -> None:
    """PostgresArtifactStorage.cleanup_old_artifacts removes only old rows."""

    storage = PostgresArtifactStorage(postgres_client=postgres_client)

    # Insert two artifacts: one "old" and one "recent".
    now = datetime.now(timezone.utc)
    old_created_at = now - timedelta(hours=5)
    recent_created_at = now - timedelta(hours=1)

    with postgres_client.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO debug_artifacts (trace_id, artifact_type, artifact_data, created_at)
                VALUES (:trace_id, :artifact_type, CAST(:artifact_data AS JSONB), :created_at)
                """
            ),
            {
                "trace_id": "test-trace-cleanup",
                "artifact_type": "query",
                "artifact_data": {"q": "old"},
                "created_at": old_created_at,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO debug_artifacts (trace_id, artifact_type, artifact_data, created_at)
                VALUES (:trace_id, :artifact_type, CAST(:artifact_data AS JSONB), :created_at)
                """
            ),
            {
                "trace_id": "test-trace-cleanup",
                "artifact_type": "answer",
                "artifact_data": {"a": "recent"},
                "created_at": recent_created_at,
            },
        )

    # Retention of 2 hours should delete the old row but keep the recent one.
    deleted = await storage.cleanup_old_artifacts(retention_hours=2)
    assert deleted >= 1

    with postgres_client.engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT trace_id, artifact_type, artifact_data
                FROM debug_artifacts
                WHERE trace_id = :trace_id
                ORDER BY created_at ASC
                """
            ),
            {"trace_id": "test-trace-cleanup"},
        )
        rows = result.fetchall()

    # Only the recent artifact should remain.
    assert len(rows) == 1
    remaining = rows[0]
    assert remaining.artifact_type == "answer"
    assert remaining.artifact_data.get("a") == "recent"
