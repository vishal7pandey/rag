from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

import pytest

from backend.api.schemas import QueryResponse
from backend.core.embedding_models import Embedding
from backend.core.generation_models import (
    QueryGenerationMetadata,
    QueryGenerationRequest,
    QueryGenerationResponse,
)
from backend.core.query_services import (
    QueryEmbeddingService,
    QueryOrchestrator,
    RetrieverService,
)
from backend.core.vector_storage import InMemoryVectorDBStorageLayer


class FakeQueryEmbeddingService(QueryEmbeddingService):
    def __init__(self, vector: List[float]) -> None:
        self._vector = vector

    async def embed_query(
        self,
        query_text: str,
        trace_context: Dict[str, Any] | None = None,
    ) -> List[float]:  # type: ignore[override]
        return list(self._vector)


class StubGenerationOrchestrator:
    async def generate_answer(
        self,
        query_request: QueryGenerationRequest,
        trace_context: dict | None = None,
    ) -> QueryGenerationResponse:
        """Return a minimal stub generation response.

        This stub avoids calling the real retrieval or LLM layers and is used
        to exercise the /api/query endpoint's integration with the
        GenerationOrchestrator in tests that focus primarily on retrieval
        behavior and filters.
        """

        meta = QueryGenerationMetadata(
            total_latency_ms=10.0,
            embedding_latency_ms=2.0,
            retrieval_latency_ms=3.0,
            prompt_assembly_latency_ms=1.0,
            generation_latency_ms=4.0,
            answer_processing_latency_ms=0.0,
            total_tokens_used=50,
            model="gpt-5-nano",
            chunks_retrieved=0,
        )

        return QueryGenerationResponse(
            query_id=uuid4(),
            answer="Stub answer",
            citations=[],
            used_chunks=[],
            metadata=meta,
        )


@pytest.mark.asyncio
async def test_query_endpoint_returns_retrieved_chunks(monkeypatch, client) -> None:
    """/api/query returns retrieved_chunks when vector store has data."""

    # Patch endpoint globals to use a dedicated in-memory storage and fake
    # embedding service, and configure a stub generation orchestrator.
    from backend.api import endpoints

    storage = InMemoryVectorDBStorageLayer()

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

    await storage.store_embedding(e1)
    await storage.store_embedding(e2)

    embedding_service = FakeQueryEmbeddingService(vector=[1.0, 0.0, 0.0])
    retriever = RetrieverService(storage=storage)
    orchestrator = QueryOrchestrator(
        embedding_service=embedding_service,
        retriever_service=retriever,
    )

    monkeypatch.setattr(endpoints, "_VECTOR_STORAGE", storage, raising=False)
    monkeypatch.setattr(
        endpoints, "_QUERY_EMBEDDING_SERVICE", embedding_service, raising=False
    )
    monkeypatch.setattr(endpoints, "_RETRIEVER_SERVICE", retriever, raising=False)
    monkeypatch.setattr(endpoints, "_QUERY_ORCHESTRATOR", orchestrator, raising=False)

    response = client.post(
        "/api/query",
        json={"query": "test query", "top_k": 2},
    )

    assert response.status_code == 200
    data = response.json()
    model = QueryResponse(**data)

    assert model.retrieved_chunks is not None
    assert len(model.retrieved_chunks) == 2

    contents = [c.content for c in model.retrieved_chunks]
    assert contents[0] == "chunk-one"
    assert contents[1] == "chunk-two"
    assert model.latency_ms >= 0.0

    # Answer should be a non-empty string.
    assert isinstance(model.answer, str)
    assert model.answer


@pytest.mark.asyncio
async def test_query_endpoint_applies_filters(monkeypatch, client) -> None:
    """/api/query respects filters provided in the public schema."""

    from backend.api import endpoints

    storage = InMemoryVectorDBStorageLayer()

    doc_id = uuid4()
    policy_emb = Embedding(
        chunk_id=uuid4(),
        document_id=doc_id,
        content="policy chunk",
        embedding=[1.0, 0.0, 0.0],
        embedding_dimension=3,
        metadata={"category": "policy"},
        quality_score=0.9,
    )
    faq_emb = Embedding(
        chunk_id=uuid4(),
        document_id=doc_id,
        content="faq chunk",
        embedding=[1.0, 0.0, 0.0],
        embedding_dimension=3,
        metadata={"category": "faq"},
        quality_score=0.8,
    )

    await storage.store_embedding(policy_emb)
    await storage.store_embedding(faq_emb)

    embedding_service = FakeQueryEmbeddingService(vector=[1.0, 0.0, 0.0])
    retriever = RetrieverService(storage=storage)
    orchestrator = QueryOrchestrator(
        embedding_service=embedding_service,
        retriever_service=retriever,
    )

    monkeypatch.setattr(endpoints, "_VECTOR_STORAGE", storage, raising=False)
    monkeypatch.setattr(
        endpoints, "_QUERY_EMBEDDING_SERVICE", embedding_service, raising=False
    )
    monkeypatch.setattr(endpoints, "_RETRIEVER_SERVICE", retriever, raising=False)
    monkeypatch.setattr(endpoints, "_QUERY_ORCHESTRATOR", orchestrator, raising=False)

    response = client.post(
        "/api/query",
        json={
            "query": "policy question",
            "top_k": 5,
            "filters": {"category": "policy"},
        },
    )

    assert response.status_code == 200
    model = QueryResponse(**response.json())

    assert model.retrieved_chunks is not None
    assert len(model.retrieved_chunks) == 1
    assert model.retrieved_chunks[0].content == "policy chunk"


@pytest.mark.asyncio
async def test_query_endpoint_no_documents_returns_friendly_message(
    monkeypatch, client
) -> None:
    """/api/query with empty vector store returns a helpful message and no citations."""

    from backend.api import endpoints

    storage = InMemoryVectorDBStorageLayer()
    embedding_service = FakeQueryEmbeddingService(vector=[1.0, 0.0, 0.0])
    retriever = RetrieverService(storage=storage)
    orchestrator = QueryOrchestrator(
        embedding_service=embedding_service,
        retriever_service=retriever,
    )

    monkeypatch.setattr(endpoints, "_VECTOR_STORAGE", storage, raising=False)
    monkeypatch.setattr(
        endpoints, "_QUERY_EMBEDDING_SERVICE", embedding_service, raising=False
    )
    monkeypatch.setattr(endpoints, "_RETRIEVER_SERVICE", retriever, raising=False)
    monkeypatch.setattr(endpoints, "_QUERY_ORCHESTRATOR", orchestrator, raising=False)

    response = client.post(
        "/api/query",
        json={"query": "test", "top_k": 5},
    )

    assert response.status_code == 200
    model = QueryResponse(**response.json())

    assert not model.citations
    assert not model.retrieved_chunks
    assert "no documents" in model.answer.lower()


@pytest.mark.asyncio
async def test_query_endpoint_include_sources_false_hides_metadata_and_citations(
    monkeypatch, client
) -> None:
    """/api/query omits metadata and citations when include_sources is False."""

    from backend.api import endpoints

    storage = InMemoryVectorDBStorageLayer()

    doc_id = uuid4()
    e1 = Embedding(
        chunk_id=uuid4(),
        document_id=doc_id,
        content="chunk-with-metadata",
        embedding=[1.0, 0.0, 0.0],
        embedding_dimension=3,
        metadata={"source": "doc.pdf", "category": "policy"},
        quality_score=0.9,
    )
    await storage.store_embedding(e1)

    embedding_service = FakeQueryEmbeddingService(vector=[1.0, 0.0, 0.0])
    retriever = RetrieverService(storage=storage)
    orchestrator = QueryOrchestrator(
        embedding_service=embedding_service,
        retriever_service=retriever,
    )

    monkeypatch.setattr(endpoints, "_VECTOR_STORAGE", storage, raising=False)
    monkeypatch.setattr(
        endpoints, "_QUERY_EMBEDDING_SERVICE", embedding_service, raising=False
    )
    monkeypatch.setattr(endpoints, "_RETRIEVER_SERVICE", retriever, raising=False)
    monkeypatch.setattr(endpoints, "_QUERY_ORCHESTRATOR", orchestrator, raising=False)

    response = client.post(
        "/api/query",
        json={"query": "test", "top_k": 5, "include_sources": False},
    )

    assert response.status_code == 200
    model = QueryResponse(**response.json())

    assert model.retrieved_chunks is not None
    assert len(model.retrieved_chunks) == 1
    # Metadata should be hidden when include_sources is False.
    assert model.retrieved_chunks[0].metadata == {}
    # Citations should also be omitted.
    assert model.citations == []
