from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.api.schemas import UploadedFileInfo
from backend.core.ingestion_models import IngestionStatus
from backend.core.ingestion_store import IngestionJobStore


def _make_uploaded_file(filename: str = "test.txt") -> UploadedFileInfo:
    return UploadedFileInfo(
        filename=filename,
        file_size_mb=1.0,
        mime_type="text/plain",
    )


def test_create_and_get_job() -> None:
    """create_job stores a PENDING job that can be retrieved."""

    store = IngestionJobStore()

    ingestion_id = uuid4()
    document_id = uuid4()
    files = [_make_uploaded_file()]

    job = store.create_job(ingestion_id, document_id, files)

    assert job.ingestion_id == ingestion_id
    assert job.document_id == document_id
    assert job.status == IngestionStatus.PENDING
    assert job.files == files

    retrieved = store.get_job(ingestion_id)
    assert retrieved is not None
    assert retrieved.ingestion_id == ingestion_id


def test_update_status_transitions_and_timestamps() -> None:
    """update_status updates status and timestamps appropriately."""

    store = IngestionJobStore()
    ingestion_id = uuid4()
    document_id = uuid4()
    files = [_make_uploaded_file()]

    job = store.create_job(ingestion_id, document_id, files)

    assert job.started_at is None
    assert job.completed_at is None

    # Move to PROCESSING should set started_at.
    store.update_status(ingestion_id, IngestionStatus.PROCESSING)
    updated = store.get_job(ingestion_id)
    assert updated is not None
    assert updated.status == IngestionStatus.PROCESSING
    assert updated.started_at is not None
    assert updated.completed_at is None

    # Move to COMPLETED should set completed_at.
    store.update_status(ingestion_id, IngestionStatus.COMPLETED)
    completed = store.get_job(ingestion_id)
    assert completed is not None
    assert completed.status == IngestionStatus.COMPLETED
    assert completed.completed_at is not None


def test_update_status_sets_error_fields() -> None:
    """Error message and stage can be stored with FAILED status."""

    store = IngestionJobStore()
    ingestion_id = uuid4()
    document_id = uuid4()
    files = [_make_uploaded_file()]

    store.create_job(ingestion_id, document_id, files)

    store.update_status(
        ingestion_id,
        IngestionStatus.FAILED,
        error_message="Something went wrong",
        error_stage="embedding",
    )

    job = store.get_job(ingestion_id)
    assert job is not None
    assert job.status == IngestionStatus.FAILED
    assert job.error_message == "Something went wrong"
    assert job.error_stage == "embedding"
    assert job.completed_at is not None


def test_update_status_unknown_job_raises_key_error() -> None:
    """Updating a non-existent job raises KeyError."""

    store = IngestionJobStore()

    with pytest.raises(KeyError):
        store.update_status(uuid4(), IngestionStatus.PROCESSING)


def test_update_metrics_accumulates_stage_and_total() -> None:
    """update_metrics stores per-stage and total durations."""

    store = IngestionJobStore()
    ingestion_id = uuid4()
    document_id = uuid4()
    files = [_make_uploaded_file()]

    store.create_job(ingestion_id, document_id, files)

    store.update_metrics(ingestion_id, "extraction", duration_ms=1000.0, pages=10)
    store.update_metrics(ingestion_id, "chunking", duration_ms=2000.0, chunks=50)

    job = store.get_job(ingestion_id)
    assert job is not None
    assert job.metrics["extraction_duration_ms"] == 1000.0
    assert job.metrics["chunking_duration_ms"] == 2000.0
    # Derived total should be approximately the sum of stage durations.
    assert job.metrics["total_duration_ms"] == pytest.approx(3000.0)
    assert job.metrics["pages"] == 10
    assert job.metrics["chunks"] == 50


def test_get_job_unknown_id_returns_none() -> None:
    """get_job returns None for an unknown ingestion_id."""

    store = IngestionJobStore()
    unknown_id = UUID("00000000-0000-0000-0000-000000000000")

    job = store.get_job(unknown_id)
    assert job is None
