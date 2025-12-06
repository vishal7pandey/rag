"""Integration tests for PostgreSQL connectivity and schema.

These tests are part of Story 003 and are intended to run against the local
Docker `db` service (pgvector) when available. If DATABASE_URL is not set or
Postgres is unreachable, the tests skip gracefully so that CI does not fail
when no database is provisioned.
"""

from __future__ import annotations

import os

import pytest

from backend.data_layer.postgres_client import PostgresClient


def _should_skip() -> str | None:
    """Return a skip reason if Postgres is not configured/available."""

    if not os.getenv("DATABASE_URL"):
        return "DATABASE_URL not set; Postgres integration tests skipped"

    try:
        client = PostgresClient()
        if not client.test_connection():
            return "Postgres not reachable; integration tests skipped"
    except Exception as exc:  # pragma: no cover - defensive
        return f"Postgres unavailable: {exc}"

    return None


@pytest.fixture(scope="module")
def postgres_client() -> PostgresClient:
    reason = _should_skip()
    if reason is not None:
        pytest.skip(reason)
    return PostgresClient()


def test_postgres_connection(postgres_client: PostgresClient) -> None:
    """Can connect to PostgreSQL (SELECT 1)."""

    assert postgres_client.test_connection() is True


def test_postgres_schema_objects_exist(postgres_client: PostgresClient) -> None:
    """Core tables, indexes, and extensions from init.sql exist."""

    results = postgres_client.verify_schema()

    # Extensions
    for ext in ("uuid-ossp", "vector", "pg_trgm"):
        assert ext in results["extensions"], f"Missing extension: {ext}"

    # Tables
    for table in (
        "documents",
        "chunks",
        "chunk_metadata",
        "retrieval_logs",
        "evaluation_feedback",
    ):
        assert table in results["tables"], f"Missing table: {table}"

    # Spot-check some important indexes
    expected_indexes = {
        "idx_documents_user_id",
        "idx_documents_created_at",
        "idx_documents_status",
        "idx_document_id",
        "idx_quality_score",
    }
    assert expected_indexes.issubset(set(results["indexes"]))
