from __future__ import annotations

from typing import Any, Dict
from uuid import UUID, uuid4

import pytest

from backend.core.embedding_models import Embedding
from backend.core.vector_storage import InMemoryVectorDBStorageLayer


def _create_sample_embedding(
    *,
    content: str = "sample content",
    metadata: Dict[str, Any] | None = None,
    document_id: UUID | None = None,
) -> Embedding:
    return Embedding(
        chunk_id=uuid4(),
        document_id=document_id or uuid4(),
        content=content,
        embedding=[0.1, 0.2, 0.3],
        metadata=metadata or {},
        quality_score=0.9,
    )


@pytest.mark.asyncio
async def test_store_single_embedding() -> None:
    """Single embedding stored successfully."""

    storage = InMemoryVectorDBStorageLayer()

    embedding = _create_sample_embedding()

    stored = await storage.store_embedding(embedding)

    assert stored is True

    retrieved = await storage.search_by_document(embedding.document_id)
    assert len(retrieved) == 1
    assert retrieved[0].embedding_id == embedding.embedding_id


@pytest.mark.asyncio
async def test_store_batch_embeddings() -> None:
    """Batch of embeddings stored successfully."""

    storage = InMemoryVectorDBStorageLayer()

    embeddings = [_create_sample_embedding() for _ in range(10)]

    result = await storage.store_embeddings_batch(embeddings)

    assert result["stored_count"] == 10
    assert result["failed_count"] == 0


@pytest.mark.asyncio
async def test_search_by_similarity() -> None:
    """Search by vector similarity returns nearest neighbors."""

    storage = InMemoryVectorDBStorageLayer()

    # Store test embeddings
    embeddings = [
        _create_sample_embedding(content="hello world"),
        _create_sample_embedding(content="hello universe"),
        _create_sample_embedding(content="goodbye world"),
    ]

    for emb in embeddings:
        await storage.store_embedding(emb)

    # Use the first embedding's vector as the query; it should be the top hit.
    query_vector = embeddings[0].embedding
    results = await storage.search_by_similarity(query_vector, top_k=2)

    assert len(results) <= 2
    assert results
    assert results[0].embedding_id == embeddings[0].embedding_id


@pytest.mark.asyncio
async def test_search_with_metadata_filters() -> None:
    """Search with metadata filters works."""

    storage = InMemoryVectorDBStorageLayer()

    e1 = _create_sample_embedding(metadata={"page_number": 0})
    e2 = _create_sample_embedding(metadata={"page_number": 1})

    await storage.store_embeddings_batch([e1, e2])

    results = await storage.search_by_similarity(
        e1.embedding,
        top_k=5,
        filters={"page_number": 0},
    )

    assert results
    assert all(r.metadata["page_number"] == 0 for r in results)


@pytest.mark.asyncio
async def test_check_duplicate_content() -> None:
    """Duplicate content detection works."""

    storage = InMemoryVectorDBStorageLayer()

    content = "This is unique content"
    e1 = _create_sample_embedding(content=content)

    await storage.store_embedding(e1)

    duplicate = await storage.check_duplicate_content(content)

    assert duplicate is not None
    assert duplicate.embedding_id == e1.embedding_id


@pytest.mark.asyncio
async def test_metadata_json_storage() -> None:
    """Metadata stored and retrieved correctly."""

    storage = InMemoryVectorDBStorageLayer()

    metadata = {
        "page_number": 5,
        "section_title": "Introduction",
        "document_type": "pdf",
        "nested": {"key": "value"},
    }

    embedding = _create_sample_embedding(metadata=metadata)

    await storage.store_embedding(embedding)

    retrieved = await storage.search_by_document(embedding.document_id)
    assert retrieved
    assert retrieved[0].metadata == metadata
