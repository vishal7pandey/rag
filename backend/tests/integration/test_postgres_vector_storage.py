from __future__ import annotations

import os
from uuid import uuid4

import pytest

from backend.core.embedding_models import Embedding
from backend.core.vector_storage_postgres import PostgresVectorDBStorageLayer
from backend.data_layer.postgres_client import PostgresClient


def _skip_reason() -> str | None:
    if not os.getenv("DATABASE_URL"):
        return "DATABASE_URL not set; Postgres vector storage integration test skipped"

    try:
        client = PostgresClient()
        if not client.test_connection():
            return "Postgres not reachable; integration test skipped"
    except Exception as exc:  # pragma: no cover
        return f"Postgres unavailable: {exc}"

    return None


@pytest.mark.asyncio
async def test_postgres_vector_storage_store_then_search_persists_across_instances() -> (
    None
):
    """Store embeddings in Postgres and verify they can be retrieved via a new storage instance.

    This approximates "restart" behavior: a new PostgresVectorDBStorageLayer should
    still find previously stored embeddings.
    """

    reason = _skip_reason()
    if reason is not None:
        pytest.skip(reason)

    # Ensure we use the same document_id for all stored chunks.
    document_id = uuid4()

    # Use simple 3-d vectors for the test (schema expects vector(1536) but pgvector
    # accepts any length only if the column is declared with that length. Our schema
    # declares vector(1536), so to avoid dimension mismatch we store a 1536-d vector.
    vec = [0.0] * 1536
    vec[0] = 1.0

    emb1 = Embedding(
        chunk_id=uuid4(),
        document_id=document_id,
        content="hello world",
        embedding=vec,
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        metadata={"language": "en", "document_type": "txt"},
        quality_score=0.9,
    )

    storage1 = PostgresVectorDBStorageLayer(PostgresClient())
    result = await storage1.store_embeddings_batch([emb1])
    assert result["stored_count"] == 1
    assert result["failed_count"] == 0

    # New instance should still see stored vectors.
    storage2 = PostgresVectorDBStorageLayer(PostgresClient())

    # Similarity query using the same vector should return at least the stored embedding.
    results = await storage2.search_by_similarity(vec, top_k=5)
    assert results
    assert any(r.chunk_id == emb1.chunk_id for r in results)

    # Also validate document lookup.
    by_doc = await storage2.search_by_document(document_id)
    assert by_doc
    assert any(r.chunk_id == emb1.chunk_id for r in by_doc)
