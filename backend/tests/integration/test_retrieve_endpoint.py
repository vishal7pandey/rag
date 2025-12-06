from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

import pytest

from backend.api.schemas import RetrievalResponse
from backend.core.embedding_models import Embedding
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


@pytest.mark.asyncio
async def test_retrieve_endpoint_success(monkeypatch, client) -> None:
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
        "/retrieve",
        json={"query": "test", "top_k": 2, "include_sources": True},
    )

    assert response.status_code == 200
    model = RetrievalResponse(**response.json())

    assert len(model.retrieved_chunks) == 2
    # Ensure order by similarity (chunk-one should be first).
    assert model.retrieved_chunks[0].content == "chunk-one"
    assert (
        model.retrieved_chunks[0].similarity_score
        >= model.retrieved_chunks[1].similarity_score
    )
    # Metrics should be populated.
    assert model.metrics.total_latency_ms >= 0.0
    assert model.metrics.results_returned == 2


@pytest.mark.asyncio
async def test_retrieve_endpoint_no_results(monkeypatch, client) -> None:
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
        "/retrieve",
        json={"query": "test", "top_k": 5},
    )

    assert response.status_code == 200
    model = RetrievalResponse(**response.json())

    assert model.retrieved_chunks == []
    assert model.metrics.results_returned == 0
    assert model.metrics.total_results_available == 0


def test_retrieve_endpoint_validation_errors(client) -> None:
    # Empty query should fail validation.
    response = client.post("/retrieve", json={"query": "", "top_k": 5})
    assert response.status_code == 422

    # top_k out of range.
    response = client.post("/retrieve", json={"query": "test", "top_k": 101})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_retrieve_endpoint_include_sources_false(monkeypatch, client) -> None:
    from backend.api import endpoints

    storage = InMemoryVectorDBStorageLayer()

    doc_id = uuid4()
    e1 = Embedding(
        chunk_id=uuid4(),
        document_id=doc_id,
        content="chunk-with-metadata",
        embedding=[1.0, 0.0, 0.0],
        embedding_dimension=3,
        metadata={"source_file": "doc.pdf", "page": 3},
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
        "/retrieve",
        json={"query": "test", "top_k": 5, "include_sources": False},
    )

    assert response.status_code == 200
    model = RetrievalResponse(**response.json())

    assert len(model.retrieved_chunks) == 1
    # When include_sources is False, source metadata should be stripped.
    assert model.retrieved_chunks[0].source == {}
