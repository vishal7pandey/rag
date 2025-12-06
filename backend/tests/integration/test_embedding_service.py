from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

import pytest

from backend.core.chunking_models import Chunk
from backend.core.embedding_models import BatchEmbeddingConfig, Embedding
from backend.core.embedding_provider import BatchEmbeddingProvider
from backend.core.embedding_service import EmbeddingService
from backend.core.vector_storage import InMemoryVectorDBStorageLayer


def _create_sample_chunk(content: str = "Sample chunk") -> Chunk:
    return Chunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content=content,
        original_content=content,
        metadata={"page_number": 0},
        token_count=10,
        word_count=2,
        char_count=len(content),
        quality_score=0.9,
    )


@pytest.mark.asyncio
async def test_full_embedding_pipeline() -> None:
    """Complete chunk → embedding → storage pipeline."""

    config = BatchEmbeddingConfig(batch_size=5, embedding_dimension=3)
    provider = BatchEmbeddingProvider(config=config)
    storage = InMemoryVectorDBStorageLayer()

    # Stub provider so we don't hit the real API.
    async def fake_embed_batch_with_metadata(
        inputs: List[Any], trace_context: Dict[str, Any] | None = None
    ) -> List[Embedding]:
        vectors = [[0.1, 0.2, 0.3] for _ in inputs]
        return [
            Embedding(
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                content=item.content,
                embedding=vec,
                embedding_dimension=config.embedding_dimension,
                metadata=item.metadata,
                quality_score=item.quality_score,
            )
            for item, vec in zip(inputs, vectors)
        ]

    provider.embed_batch_with_metadata = fake_embed_batch_with_metadata  # type: ignore[assignment]

    service = EmbeddingService(provider=provider, storage=storage)

    chunks = [_create_sample_chunk(f"Chunk {i}") for i in range(5)]

    result = await service.embed_and_store(chunks, config)

    assert result.successful_embeddings == 5
    assert result.failed_embeddings == 0
    assert len(result.embeddings) == 5

    # Embeddings should be persisted in the storage layer.
    doc_id = chunks[0].document_id
    stored = await storage.search_by_document(doc_id)
    assert stored


@pytest.mark.asyncio
async def test_embedding_service_skips_duplicates() -> None:
    """Service skips already-embedded content when configured to do so."""

    config = BatchEmbeddingConfig(
        batch_size=5, embedding_dimension=3, skip_duplicate_content=True
    )
    provider = BatchEmbeddingProvider(config=config)
    storage = InMemoryVectorDBStorageLayer()

    # Pre-store an embedding for some content.
    duplicate_content = "Duplicate content"
    existing_embedding = Embedding(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content=duplicate_content,
        embedding=[0.1, 0.2, 0.3],
        embedding_dimension=config.embedding_dimension,
        metadata={},
        quality_score=0.9,
    )
    await storage.store_embedding(existing_embedding)

    # Stub provider; should not be called for the duplicate chunk.
    async def fake_embed_batch_with_metadata(
        inputs: List[Any], trace_context: Dict[str, Any] | None = None
    ) -> List[Embedding]:
        pytest.fail("Provider should not be called for duplicate content")

    provider.embed_batch_with_metadata = fake_embed_batch_with_metadata  # type: ignore[assignment]

    service = EmbeddingService(provider=provider, storage=storage)

    chunks = [_create_sample_chunk(duplicate_content)]

    result = await service.embed_and_store(chunks, config)

    assert result.successful_embeddings == 0
    assert result.failed_embeddings == 0
    assert result.embeddings == []
    assert result.quality_metrics["duplicates_skipped"] == 1


@pytest.mark.asyncio
async def test_embedding_service_metrics() -> None:
    """Service calculates basic metrics for embeddings."""

    config = BatchEmbeddingConfig(batch_size=5, embedding_dimension=3)
    provider = BatchEmbeddingProvider(config=config)
    storage = InMemoryVectorDBStorageLayer()

    async def fake_embed_batch_with_metadata(
        inputs: List[Any], trace_context: Dict[str, Any] | None = None
    ) -> List[Embedding]:
        vectors = [[0.1, 0.2, 0.3] for _ in inputs]
        return [
            Embedding(
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                content=item.content,
                embedding=vec,
                embedding_dimension=config.embedding_dimension,
                metadata=item.metadata,
                quality_score=item.quality_score,
            )
            for item, vec in zip(inputs, vectors)
        ]

    provider.embed_batch_with_metadata = fake_embed_batch_with_metadata  # type: ignore[assignment]

    service = EmbeddingService(provider=provider, storage=storage)

    chunks = [_create_sample_chunk(f"Chunk {i}") for i in range(3)]

    result = await service.embed_and_store(chunks, config)

    assert result.total_inputs == 3
    assert result.successful_embeddings == 3
    assert result.failed_embeddings == 0
    assert result.quality_metrics["tokens_used_estimate"] == sum(
        c.token_count for c in chunks
    )
    assert result.quality_metrics["valid_embeddings"] == 3
    assert result.embedding_duration_ms >= 0.0
    assert result.storage_duration_ms >= 0.0
    assert result.total_duration_ms >= result.embedding_duration_ms
