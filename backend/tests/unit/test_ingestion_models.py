from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List
from uuid import uuid4

from backend.api.schemas import UploadedFileInfo
from backend.core.chunking_models import Chunk
from backend.core.ingestion_models import IngestionJob, IngestionStatus


def _make_uploaded_file(filename: str = "test.txt") -> UploadedFileInfo:
    return UploadedFileInfo(
        filename=filename,
        file_size_mb=1.0,
        mime_type="text/plain",
    )


def test_ingestion_job_initial_progress_and_chunks_created() -> None:
    """New jobs start at 0% progress with no chunks created."""

    ingestion_id = uuid4()
    document_id = uuid4()
    files: List[UploadedFileInfo] = [_make_uploaded_file()]

    job = IngestionJob(
        ingestion_id=ingestion_id,
        document_id=document_id,
        status=IngestionStatus.PENDING,
        files=files,
    )

    assert job.progress_percent == 0
    assert job.chunks_created == 0


def test_ingestion_job_processing_progress_increases_with_metrics() -> None:
    """Processing progress reflects completed stages based on metrics."""

    ingestion_id = uuid4()
    document_id = uuid4()
    files: List[UploadedFileInfo] = [_make_uploaded_file()]

    job = IngestionJob(
        ingestion_id=ingestion_id,
        document_id=document_id,
        status=IngestionStatus.PROCESSING,
        files=files,
    )

    # No stage metrics yet: should be the base processing progress (~25%).
    base_progress = job.progress_percent
    assert 20 <= base_progress <= 30

    # Mark extraction as completed.
    job.metrics["extraction_duration_ms"] = 1000.0
    progress_after_extraction = job.progress_percent
    assert progress_after_extraction > base_progress

    # Mark all stages as completed.
    job.metrics.update(
        {
            "chunking_duration_ms": 2000.0,
            "embedding_duration_ms": 3000.0,
            "storage_duration_ms": 4000.0,
        }
    )
    progress_after_all = job.progress_percent
    assert progress_after_all > progress_after_extraction
    assert progress_after_all <= 99


def test_ingestion_job_failed_has_progress_at_least_50_percent() -> None:
    """FAILED jobs report at least 50% progress."""

    ingestion_id = uuid4()
    document_id = uuid4()
    files: List[UploadedFileInfo] = [_make_uploaded_file()]

    job = IngestionJob(
        ingestion_id=ingestion_id,
        document_id=document_id,
        status=IngestionStatus.FAILED,
        files=files,
    )

    assert job.progress_percent >= 50


def test_ingestion_job_total_duration_ms_uses_completed_at_when_set() -> None:
    """total_duration_ms uses completed_at when available."""

    ingestion_id = uuid4()
    document_id = uuid4()
    files: List[UploadedFileInfo] = [_make_uploaded_file()]

    created_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    completed_at = created_at + timedelta(seconds=5)

    job = IngestionJob(
        ingestion_id=ingestion_id,
        document_id=document_id,
        status=IngestionStatus.COMPLETED,
        files=files,
        created_at=created_at,
        completed_at=completed_at,
    )

    duration_ms = job.total_duration_ms
    assert 4000 <= duration_ms <= 6000


def test_ingestion_job_chunks_created_counts_list_length() -> None:
    """chunks_created is derived from the number of chunks in the job."""

    ingestion_id = uuid4()
    document_id = uuid4()
    files: List[UploadedFileInfo] = [_make_uploaded_file()]

    job = IngestionJob(
        ingestion_id=ingestion_id,
        document_id=document_id,
        status=IngestionStatus.PROCESSING,
        files=files,
    )

    assert job.chunks_created == 0

    # Add some chunks and ensure the property reflects the updated list.
    job.chunks.extend(
        [
            Chunk(
                chunk_id=uuid4(),
                document_id=document_id,
                content="chunk-1",
                original_content="chunk-1",
                metadata={},
                token_count=10,
                word_count=2,
                char_count=7,
                quality_score=0.9,
            ),
            Chunk(
                chunk_id=uuid4(),
                document_id=document_id,
                content="chunk-2",
                original_content="chunk-2",
                metadata={},
                token_count=8,
                word_count=2,
                char_count=7,
                quality_score=0.8,
            ),
        ]
    )

    assert job.chunks_created == 2
