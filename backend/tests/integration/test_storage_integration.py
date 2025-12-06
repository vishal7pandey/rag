"""Integration tests for full chunk storage across Pinecone + PostgreSQL."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from backend.api.schemas import Chunk
from backend.data_layer.postgres_client import PostgresClient
from backend.data_layer.storage_service import StorageService


def _skip_reason() -> str | None:
    if not os.getenv("DATABASE_URL"):
        return "DATABASE_URL not set; storage integration tests skipped"
    if not os.getenv("PINECONE_API_KEY"):
        return "PINECONE_API_KEY not set; storage integration tests skipped"

    try:
        pg = PostgresClient()
        if not pg.test_connection():
            return "Postgres not reachable; storage integration tests skipped"
    except Exception as exc:  # pragma: no cover
        return f"Postgres unavailable: {exc}"

    return None


@pytest.fixture(scope="module")
def storage_service() -> StorageService:
    reason = _skip_reason()
    if reason is not None:
        pytest.skip(reason)
    return StorageService()


def _make_test_chunk() -> Chunk:
    return Chunk(
        id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content="This is a test chunk for storage verification.",
        dense_embedding=[0.1] * 16,  # Shorter than 1536, but fine for Pinecone test
        sparse_embedding={"test": 1.0},
        metadata={
            "source": "test.pdf",
            "page_number": 1,
            "language": "en",
            "user_id": "user-1",
        },
        quality_score=0.9,
        embedding_model="text-embedding-3-small",
        created_at=None,
        updated_at=None,
    )


def test_store_single_chunk(storage_service: StorageService) -> None:
    """Can store a chunk in both Pinecone and PostgreSQL."""

    chunk = _make_test_chunk()
    result = storage_service.store_chunk(chunk)

    assert result["pinecone_success"] is True
    assert result["postgres_success"] is True


def test_retrieve_chunk_by_id(storage_service: StorageService) -> None:
    """Can retrieve a previously stored chunk from PostgreSQL by ID."""

    chunk = _make_test_chunk()
    storage_service.store_chunk(chunk)

    retrieved = storage_service.get_chunk_by_id(chunk.id)

    assert retrieved is not None
    assert retrieved.id == chunk.id
    assert retrieved.document_id == chunk.document_id
    assert retrieved.content == chunk.content
