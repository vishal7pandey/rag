from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

import pytest

from backend.core.embedding_models import Embedding
from backend.core.query_models import QueryRequest
from backend.core.query_services import (
    QueryEmbeddingService,
    QueryOrchestrator,
    RetrieverService,
)
from backend.core.vector_storage import InMemoryVectorDBStorageLayer


class FakeQueryEmbeddingService(QueryEmbeddingService):
    """Deterministic embedding service for tests.

    Produces low-dimensional vectors so we can reason about cosine similarity.
    """

    def __init__(self, vector: List[float]) -> None:
        self._vector = vector

    async def embed_query(
        self,
        query_text: str,
        trace_context: Dict[str, Any] | None = None,
    ) -> List[float]:  # type: ignore[override]
        return list(self._vector)


@pytest.mark.asyncio
async def test_query_orchestrator_returns_ranked_results() -> None:
    """Orchestrator embeds query and returns ranked similar chunks."""

    storage = InMemoryVectorDBStorageLayer()

    # Prepare embeddings: e1 is closest to query, then e2, then e3.
    doc_id = uuid4()
    e1 = Embedding(
        chunk_id=uuid4(),
        document_id=doc_id,
        content="chunk-one",
        embedding=[1.0, 0.0, 0.0],
        embedding_dimension=3,
        metadata={"label": "one"},
        quality_score=0.9,
    )
    e2 = Embedding(
        chunk_id=uuid4(),
        document_id=doc_id,
        content="chunk-two",
        embedding=[0.8, 0.2, 0.0],
        embedding_dimension=3,
        metadata={"label": "two"},
        quality_score=0.8,
    )
    e3 = Embedding(
        chunk_id=uuid4(),
        document_id=doc_id,
        content="chunk-three",
        embedding=[0.0, 1.0, 0.0],
        embedding_dimension=3,
        metadata={"label": "three"},
        quality_score=0.7,
    )

    await storage.store_embedding(e1)
    await storage.store_embedding(e2)
    await storage.store_embedding(e3)

    embedding_service = FakeQueryEmbeddingService(vector=[1.0, 0.0, 0.0])
    retriever = RetrieverService(storage=storage)
    orchestrator = QueryOrchestrator(
        embedding_service=embedding_service,
        retriever_service=retriever,
    )

    request = QueryRequest(
        query_id=uuid4(),
        query_text="test query",
        top_k=2,
        search_type="dense",
    )

    response = await orchestrator.query(request)

    assert response.query_id == request.query_id
    assert len(response.retrieved_chunks) == 2

    # First result should be e1, second should be e2 based on cosine similarity.
    first, second = response.retrieved_chunks
    assert first.content == "chunk-one"
    assert second.content == "chunk-two"
    assert first.rank == 1
    assert second.rank == 2
    assert response.metrics["search_type"] == "dense"
    assert response.metrics["total_results_available"] == 2
    assert response.metrics["total_latency_ms"] >= 0.0


@pytest.mark.asyncio
async def test_retriever_applies_filters() -> None:
    """Retriever respects metadata filters when searching."""

    storage = InMemoryVectorDBStorageLayer()

    doc_id = uuid4()
    policy_embedding = Embedding(
        chunk_id=uuid4(),
        document_id=doc_id,
        content="policy text",
        embedding=[0.9, 0.0, 0.0],
        embedding_dimension=3,
        metadata={"category": "policy"},
        quality_score=0.9,
    )
    faq_embedding = Embedding(
        chunk_id=uuid4(),
        document_id=doc_id,
        content="faq text",
        embedding=[0.9, 0.0, 0.0],
        embedding_dimension=3,
        metadata={"category": "faq"},
        quality_score=0.8,
    )

    await storage.store_embedding(policy_embedding)
    await storage.store_embedding(faq_embedding)

    embedding_service = FakeQueryEmbeddingService(vector=[0.9, 0.0, 0.0])
    retriever = RetrieverService(storage=storage)
    orchestrator = QueryOrchestrator(
        embedding_service=embedding_service,
        retriever_service=retriever,
    )

    request = QueryRequest(
        query_id=uuid4(),
        query_text="policy question",
        top_k=5,
        search_type="dense",
        filters={"category": "policy"},
    )

    response = await orchestrator.query(request)

    assert len(response.retrieved_chunks) == 1
    chunk = response.retrieved_chunks[0]
    assert chunk.metadata.get("category") == "policy"
