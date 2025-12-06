"""Integration tests for PostgreSQL CRUD operations on Story 003 schema."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from backend.data_layer.postgres_client import PostgresClient


def _skip_reason() -> str | None:
    if not os.getenv("DATABASE_URL"):
        return "DATABASE_URL not set; Postgres operation tests skipped"
    try:
        client = PostgresClient()
        if not client.test_connection():
            return "Postgres not reachable; Postgres operation tests skipped"
    except Exception as exc:  # pragma: no cover
        return f"Postgres unavailable: {exc}"
    return None


@pytest.fixture(scope="module")
def postgres_client() -> PostgresClient:
    reason = _skip_reason()
    if reason is not None:
        pytest.skip(reason)
    return PostgresClient()


def test_documents_insert_select_update_delete(postgres_client: PostgresClient) -> None:
    """Basic CRUD cycle on the documents table."""

    doc_id = uuid4()

    with postgres_client.engine.begin() as conn:
        # Insert
        conn.execute(
            text(
                """
                INSERT INTO documents (id, filename, document_type, total_chunks)
                VALUES (:id, :filename, :document_type, :total_chunks)
                """
            ),
            {
                "id": str(doc_id),
                "filename": "crud_test.pdf",
                "document_type": "pdf",
                "total_chunks": 1,
            },
        )

        # Select
        result = conn.execute(
            text(
                "SELECT filename, document_type, total_chunks FROM documents WHERE id = :id"
            ),
            {"id": str(doc_id)},
        )
        row = result.fetchone()
        assert row is not None
        assert row.filename == "crud_test.pdf"

        # Update
        conn.execute(
            text("UPDATE documents SET total_chunks = :n WHERE id = :id"),
            {"id": str(doc_id), "n": 2},
        )
        result = conn.execute(
            text("SELECT total_chunks FROM documents WHERE id = :id"),
            {"id": str(doc_id)},
        )
        assert result.scalar() == 2

        # Delete
        conn.execute(text("DELETE FROM documents WHERE id = :id"), {"id": str(doc_id)})
        result = conn.execute(
            text("SELECT 1 FROM documents WHERE id = :id"), {"id": str(doc_id)}
        )
        assert result.fetchone() is None
