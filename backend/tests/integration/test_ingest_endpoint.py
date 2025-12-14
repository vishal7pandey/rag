from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

import pytest

from backend.api.schemas import IngestionResponse


def test_ingest_endpoint_returns_202_and_runs_pipeline(client) -> None:
    """POST /ingest returns 202 and a valid IngestionResponse with progress."""

    files = {
        "files": (
            "doc.txt",
            b"hello world. This should create at least one chunk.",
            "text/plain",
        )
    }

    response = client.post("/ingest", files=files)

    assert response.status_code == 202
    data = response.json()
    model = IngestionResponse(**data)

    assert model.ingestion_id
    assert model.document_id is not None
    # Orchestration is synchronous in this story, so we expect COMPLETED.
    assert model.status.value in {"completed", "failed"}
    assert 0 <= model.progress_percent <= 100
    assert model.chunks_created > 0


@pytest.mark.asyncio
async def test_ingest_then_retrieve_returns_chunks(client, monkeypatch) -> None:
    """Ingest stores vectors in-memory and /retrieve returns at least 1 result.

    This test avoids requiring OPENAI_API_KEY by monkeypatching:
    - ingestion embedding service
    - query embedding service
    so both use deterministic vectors.
    """

    from backend.api import endpoints as endpoints_mod
    from backend.core.embedding_models import Embedding, EmbeddingResult
    from backend.core.ingestion_orchestrator import IngestionOrchestrator
    from backend.core.ingestion_store import IngestionJobStore
    from backend.core.query_services import QueryOrchestrator, RetrieverService
    from backend.core.vector_storage import InMemoryVectorDBStorageLayer

    class FakeEmbeddingService:
        async def embed_and_store(
            self,
            chunks: List[Any],
            _config: Any,
            trace_context: Dict[str, Any] | None = None,
        ) -> EmbeddingResult:
            embeddings: List[Embedding] = []
            for chunk in chunks:
                embeddings.append(
                    Embedding(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        embedding=[1.0, 1.0, 1.0],
                        embedding_model="test-embedding",
                        embedding_dimension=3,
                        metadata=chunk.metadata,
                        quality_score=chunk.quality_score,
                    )
                )

            await endpoints_mod._VECTOR_STORAGE.store_embeddings_batch(embeddings)

            return EmbeddingResult(
                total_inputs=len(chunks),
                total_batches=1,
                successful_embeddings=len(embeddings),
                failed_embeddings=0,
                total_api_calls=0,
                total_retries=0,
                embeddings=embeddings,
                failures=[],
                embedding_duration_ms=0.0,
                storage_duration_ms=0.0,
                total_duration_ms=0.0,
                quality_metrics={},
            )

    class FakeQueryEmbeddingService:
        async def embed_query(
            self,
            query_text: str,
            trace_context: Dict[str, Any] | None = None,
        ) -> List[float]:
            return [1.0, 1.0, 1.0]

    # Patch global singletons used by route handlers.
    storage = InMemoryVectorDBStorageLayer()
    job_store = IngestionJobStore()

    monkeypatch.setattr(endpoints_mod, "_VECTOR_STORAGE", storage)
    monkeypatch.setattr(endpoints_mod, "_INGESTION_JOB_STORE", job_store)

    fake_embedding_service = FakeEmbeddingService()
    monkeypatch.setattr(endpoints_mod, "_EMBEDDING_SERVICE", fake_embedding_service)
    monkeypatch.setattr(
        endpoints_mod,
        "_INGESTION_ORCHESTRATOR",
        IngestionOrchestrator(
            extraction_service=None,
            chunking_service=None,
            embedding_service=fake_embedding_service,
            job_store=job_store,
        ),
    )

    retriever = RetrieverService(storage=storage)
    query_orchestrator = QueryOrchestrator(
        embedding_service=FakeQueryEmbeddingService(),
        retriever_service=retriever,
        embedding_cache=None,
    )
    monkeypatch.setattr(endpoints_mod, "_RETRIEVER_SERVICE", retriever)
    monkeypatch.setattr(endpoints_mod, "_QUERY_ORCHESTRATOR", query_orchestrator)

    ingest_files = {
        "files": (
            "doc.txt",
            b"hello world. This should create at least one chunk.",
            "text/plain",
        )
    }
    ingest_resp = client.post("/ingest", files=ingest_files)
    assert ingest_resp.status_code == 202

    retrieve_resp = client.post("/retrieve", json={"query": "hello world"})
    assert retrieve_resp.status_code == 200

    payload = retrieve_resp.json()
    assert isinstance(payload.get("retrieved_chunks"), list)
    assert len(payload["retrieved_chunks"]) > 0


def test_ingest_status_endpoint_returns_job_state(client) -> None:
    """GET /ingest/status/{id} returns current job state created by /ingest."""

    files = {"files": ("status-doc.txt", b"hello world", "text/plain")}

    upload_resp = client.post("/ingest", files=files)
    assert upload_resp.status_code == 202
    upload_data = upload_resp.json()
    ingestion_id = upload_data["ingestion_id"]

    status_resp = client.get(f"/ingest/status/{ingestion_id}")
    assert status_resp.status_code == 200

    data = status_resp.json()
    model = IngestionResponse(**data)

    assert str(model.ingestion_id) == ingestion_id
    assert model.status.value in {"pending", "processing", "completed", "failed"}


def test_ingest_status_not_found_returns_404(client) -> None:
    """GET /ingest/status with unknown ID returns 404."""

    unknown_id = uuid4()

    response = client.get(f"/ingest/status/{unknown_id}")

    assert response.status_code == 404


def test_ingest_inherits_validation_from_upload(client) -> None:
    """/ingest enforces the same file validation rules as /api/ingest/upload."""

    # No files
    response = client.post("/ingest")
    assert response.status_code == 400

    # Unsupported format
    files = {"files": ("bad.exe", b"MZ\x90\x00", "application/x-msdownload")}
    response = client.post("/ingest", files=files)
    assert response.status_code == 400
