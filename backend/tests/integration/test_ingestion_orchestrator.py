from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Tuple
from uuid import uuid4

import pytest
from unittest.mock import MagicMock

from backend.api.schemas import DocumentMetadata, IngestionConfig, UploadedFileInfo
from backend.core.chunking_models import Chunk
from backend.core.ingestion_models import IngestionStatus
from backend.core.ingestion_orchestrator import IngestionOrchestrator
from backend.core.ingestion_store import IngestionJobStore


def _make_uploaded_file(filename: str = "test.txt") -> UploadedFileInfo:
    return UploadedFileInfo(
        filename=filename,
        file_size_mb=1.0,
        mime_type="text/plain",
    )


@pytest.mark.asyncio
async def test_full_pipeline_success() -> None:
    """Complete ingestion from files to embedded results."""

    # Arrange job and config
    job_store = IngestionJobStore()
    ingestion_id = uuid4()
    document_id = uuid4()
    files_meta = [_make_uploaded_file()]
    job = job_store.create_job(ingestion_id, document_id, files_meta)

    files: List[Tuple[str, bytes]] = [(files_meta[0].filename, b"hello world")]
    metadata = DocumentMetadata(category="test", language="en")
    config = IngestionConfig(chunk_size_tokens=128, chunk_overlap_tokens=16)

    # Mock extraction result
    extracted_doc = SimpleNamespace(
        document_id=document_id,
        total_pages=1,
        pages=[],
        format="txt",
    )
    extraction_service = MagicMock()
    extraction_service.extract.return_value = extracted_doc

    # Mock chunking result
    chunk1 = Chunk(
        chunk_id=uuid4(),
        document_id=document_id,
        content="chunk-1",
        original_content="chunk-1",
        metadata={},
        token_count=10,
        word_count=2,
        char_count=7,
        quality_score=0.9,
    )
    chunk2 = Chunk(
        chunk_id=uuid4(),
        document_id=document_id,
        content="chunk-2",
        original_content="chunk-2",
        metadata={},
        token_count=8,
        word_count=2,
        char_count=7,
        quality_score=0.8,
    )
    chunk_result = SimpleNamespace(
        chunks=[chunk1, chunk2],
        chunking_duration_ms=123.0,
    )
    chunking_service = MagicMock()
    chunking_service.chunk_document.return_value = chunk_result

    # Mock embedding result (embeddings + metrics)
    async def fake_embed_and_store(
        chunks: List[Chunk],
        embedding_config: IngestionConfig,
        trace_context: Dict[str, Any] | None = None,
    ) -> Any:
        return SimpleNamespace(
            embeddings=["e1", "e2"],
            embedding_duration_ms=456.0,
            quality_metrics={
                "tokens_used_estimate": sum(c.token_count for c in chunks)
            },
        )

    embedding_service = SimpleNamespace()
    embedding_service.embed_and_store = fake_embed_and_store

    orchestrator = IngestionOrchestrator(
        extraction_service=extraction_service,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        job_store=job_store,
    )

    # Act
    result_job = await orchestrator.ingest_and_store(
        job_id=job.ingestion_id,
        files=files,
        document_metadata=metadata,
        ingestion_config=config,
    )

    # Assert
    assert result_job.status == IngestionStatus.COMPLETED
    assert len(result_job.chunks) == 2
    assert len(result_job.embeddings) == 2
    assert result_job.metrics["extraction_duration_ms"] >= 0.0
    assert result_job.metrics["chunking_duration_ms"] == pytest.approx(123.0)
    assert result_job.metrics["tokens_used_estimate"] == 18


@pytest.mark.asyncio
async def test_extraction_failure_marks_job_failed() -> None:
    """Job marked FAILED if extraction raises an exception."""

    job_store = IngestionJobStore()
    ingestion_id = uuid4()
    document_id = uuid4()
    files_meta = [_make_uploaded_file()]
    job_store.create_job(ingestion_id, document_id, files_meta)

    files: List[Tuple[str, bytes]] = [(files_meta[0].filename, b"bad bytes")]
    metadata = DocumentMetadata(category="test", language="en")
    config = IngestionConfig()

    extraction_service = MagicMock()
    extraction_service.extract.side_effect = RuntimeError("Invalid PDF")

    orchestrator = IngestionOrchestrator(
        extraction_service=extraction_service,
        chunking_service=MagicMock(),
        embedding_service=None,
        job_store=job_store,
    )

    result_job = await orchestrator.ingest_and_store(
        job_id=ingestion_id,
        files=files,
        document_metadata=metadata,
        ingestion_config=config,
    )

    assert result_job.status == IngestionStatus.FAILED
    assert result_job.error_stage == "extraction"
    assert "Invalid PDF" in (result_job.error_message or "")


@pytest.mark.asyncio
async def test_embedding_failure_marks_job_failed_after_chunking() -> None:
    """Chunks are created even if embedding fails; job marked FAILED at embedding stage."""

    job_store = IngestionJobStore()
    ingestion_id = uuid4()
    document_id = uuid4()
    files_meta = [_make_uploaded_file()]
    job_store.create_job(ingestion_id, document_id, files_meta)

    files: List[Tuple[str, bytes]] = [(files_meta[0].filename, b"hello world")]
    metadata = DocumentMetadata(category="test", language="en")
    config = IngestionConfig()

    extracted_doc = SimpleNamespace(
        document_id=document_id,
        total_pages=1,
        pages=[],
        format="txt",
    )
    extraction_service = MagicMock()
    extraction_service.extract.return_value = extracted_doc

    chunk = Chunk(
        chunk_id=uuid4(),
        document_id=document_id,
        content="chunk-1",
        original_content="chunk-1",
        metadata={},
        token_count=10,
        word_count=2,
        char_count=7,
        quality_score=0.9,
    )
    chunk_result = SimpleNamespace(chunks=[chunk], chunking_duration_ms=50.0)
    chunking_service = MagicMock()
    chunking_service.chunk_document.return_value = chunk_result

    async def failing_embed_and_store(
        chunks: List[Chunk],
        embedding_config: IngestionConfig,
        trace_context: Dict[str, Any] | None = None,
    ) -> Any:
        raise RuntimeError("Rate limited")

    embedding_service = SimpleNamespace()
    embedding_service.embed_and_store = failing_embed_and_store

    orchestrator = IngestionOrchestrator(
        extraction_service=extraction_service,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        job_store=job_store,
    )

    result_job = await orchestrator.ingest_and_store(
        job_id=ingestion_id,
        files=files,
        document_metadata=metadata,
        ingestion_config=config,
    )

    assert result_job.status == IngestionStatus.FAILED
    assert result_job.error_stage == "embedding"
    assert len(result_job.chunks) == 1  # Chunking still succeeded


@pytest.mark.asyncio
async def test_ingestion_orchestrator_metrics_aggregation() -> None:
    """Metrics are collected across stages."""

    job_store = IngestionJobStore()
    ingestion_id = uuid4()
    document_id = uuid4()
    files_meta = [_make_uploaded_file()]
    job_store.create_job(ingestion_id, document_id, files_meta)

    files: List[Tuple[str, bytes]] = [(files_meta[0].filename, b"hello world")]
    metadata = DocumentMetadata(category="test", language="en")
    config = IngestionConfig()

    extracted_doc = SimpleNamespace(
        document_id=document_id,
        total_pages=1,
        pages=[],
        format="txt",
    )
    extraction_service = MagicMock()
    extraction_service.extract.return_value = extracted_doc

    chunk = Chunk(
        chunk_id=uuid4(),
        document_id=document_id,
        content="chunk-1",
        original_content="chunk-1",
        metadata={},
        token_count=10,
        word_count=2,
        char_count=7,
        quality_score=0.9,
    )
    chunk_result = SimpleNamespace(chunks=[chunk], chunking_duration_ms=50.0)
    chunking_service = MagicMock()
    chunking_service.chunk_document.return_value = chunk_result

    async def fake_embed_and_store(
        chunks: List[Chunk],
        embedding_config: IngestionConfig,
        trace_context: Dict[str, Any] | None = None,
    ) -> Any:
        return SimpleNamespace(
            embeddings=["e1"],
            embedding_duration_ms=75.0,
            quality_metrics={
                "tokens_used_estimate": sum(c.token_count for c in chunks)
            },
        )

    embedding_service = SimpleNamespace()
    embedding_service.embed_and_store = fake_embed_and_store

    orchestrator = IngestionOrchestrator(
        extraction_service=extraction_service,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        job_store=job_store,
    )

    result_job = await orchestrator.ingest_and_store(
        job_id=ingestion_id,
        files=files,
        document_metadata=metadata,
        ingestion_config=config,
    )

    assert result_job.status == IngestionStatus.COMPLETED
    assert result_job.metrics["extraction_duration_ms"] > 0
    assert result_job.metrics["chunking_duration_ms"] == pytest.approx(50.0)
    assert result_job.metrics["embedding_duration_ms"] == pytest.approx(75.0)
    assert result_job.metrics["tokens_used_estimate"] == 10
