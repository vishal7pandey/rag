from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from backend.api.schemas import UploadedFileInfo
from backend.core.ingestion_models import IngestionJob, IngestionStatus


class IngestionJobStore:
    """In-memory job store for the ingestion pipeline.

    This store is intentionally simple for Story 010: jobs are kept in a
    process-local dictionary with no TTL or persistence. Future stories can
    replace or extend this with a database-backed implementation.
    """

    def __init__(self) -> None:
        self._jobs: Dict[UUID, IngestionJob] = {}

    def create_job(
        self,
        ingestion_id: UUID,
        document_id: UUID,
        files: list[UploadedFileInfo],
    ) -> IngestionJob:
        """Create and store a new ingestion job in PENDING state."""

        job = IngestionJob(
            ingestion_id=ingestion_id,
            document_id=document_id,
            status=IngestionStatus.PENDING,
            files=files,
            created_at=datetime.now(timezone.utc),
        )
        self._jobs[ingestion_id] = job
        return job

    def get_job(self, ingestion_id: UUID) -> Optional[IngestionJob]:
        """Retrieve a job by ID, or ``None`` if not found."""

        return self._jobs.get(ingestion_id)

    def update_status(
        self,
        ingestion_id: UUID,
        status: IngestionStatus,
        error_message: Optional[str] = None,
        error_stage: Optional[str] = None,
    ) -> None:
        """Update the status and optional error fields for a job.

        Raises ``KeyError`` if the job does not exist.
        """

        job = self._jobs.get(ingestion_id)
        if job is None:
            raise KeyError(f"Job {ingestion_id} not found")

        job.status = status
        if error_message is not None:
            job.error_message = error_message
        if error_stage is not None:
            job.error_stage = error_stage

        if status == IngestionStatus.PROCESSING and job.started_at is None:
            job.started_at = datetime.now(timezone.utc)
        if status in {IngestionStatus.COMPLETED, IngestionStatus.FAILED}:
            job.completed_at = datetime.now(timezone.utc)

    def update_metrics(
        self,
        ingestion_id: UUID,
        stage: str,
        duration_ms: float,
        **extra_metrics: Any,
    ) -> None:
        """Accumulate metrics for a given stage on the job.

        ``stage`` is a logical name such as "extraction", "chunking",
        "embedding", or "storage"; metrics are stored using
        ``{stage}_duration_ms`` plus any additional key/value pairs.
        """

        job = self._jobs.get(ingestion_id)
        if job is None:
            raise KeyError(f"Job {ingestion_id} not found")

        key = f"{stage}_duration_ms"
        job.metrics[key] = float(duration_ms)

        for metric_key, metric_value in extra_metrics.items():
            job.metrics[metric_key] = metric_value

        # Optionally maintain a derived total duration across stages. This is
        # approximate, but sufficient for status reporting.
        stage_keys = [
            "extraction_duration_ms",
            "chunking_duration_ms",
            "embedding_duration_ms",
            "storage_duration_ms",
        ]
        total = 0.0
        for k in stage_keys:
            value = job.metrics.get(k)
            if isinstance(value, (int, float)):
                total += float(value)
        job.metrics["total_duration_ms"] = total
