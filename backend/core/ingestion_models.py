from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from backend.core.chunking_models import Chunk
from backend.core.data_models import ExtractedDocument

if TYPE_CHECKING:
    from backend.api.schemas import UploadedFileInfo
    from backend.core.ingestion_store import IngestionJobStore


class IngestionStatus(str, Enum):
    """Ingestion pipeline status.

    This is an internal status enum used by the orchestration layer. The
    values are lowercase strings for easy JSON serialization.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IngestionJob:
    """In-memory representation of an ingestion job.

    This model tracks the lifecycle and metrics of a single ingestion run
    from upload through extraction, chunking, embedding, and storage.
    """

    ingestion_id: UUID
    document_id: UUID
    status: IngestionStatus
    files: List["UploadedFileInfo"]

    # Pipeline state
    extracted_document: Optional[ExtractedDocument] = None
    chunks: List[Chunk] = field(default_factory=list)
    # Embeddings generated for this job. Typed as List[Any] here to avoid a
    # hard dependency on the embedding layer in this story; later stories may
    # refine this to a concrete Embedding model once the embedding layer is
    # present on this branch.
    embeddings: List[Any] = field(default_factory=list)

    # Metrics by stage
    metrics: Dict[str, Any] = field(default_factory=dict)

    # Error tracking
    error_message: Optional[str] = None
    error_stage: Optional[str] = (
        None  # "extraction", "chunking", "embedding", "storage"
    )

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def progress_percent(self) -> int:
        """Compute progress based on current stage and recorded metrics.

        The mapping is intentionally coarse-grained and heuristic:
        - PENDING → 0%
        - PROCESSING → estimated based on which stage metrics are present
        - COMPLETED → 100%
        - FAILED → at least 50%, or the current processing estimate, whichever is greater
        """

        stage_progress = {
            IngestionStatus.PENDING: 0,
            IngestionStatus.PROCESSING: self._compute_processing_progress(),
            IngestionStatus.COMPLETED: 100,
            IngestionStatus.FAILED: max(50, self._compute_processing_progress()),
        }
        return stage_progress.get(self.status, 0)

    def _compute_processing_progress(self) -> int:
        """Estimate progress during PROCESSING based on which stages have metrics.

        We count completed stages among:
        - extraction_duration_ms
        - chunking_duration_ms
        - embedding_duration_ms
        - storage_duration_ms
        and map that to a value between ~25% and ~99%.
        """

        completed_keys = [
            "extraction_duration_ms",
            "chunking_duration_ms",
            "embedding_duration_ms",
            "storage_duration_ms",
        ]
        stages_completed = sum(1 for key in completed_keys if key in self.metrics)
        # Start at 25% once processing begins, add 20% per completed stage, cap below 100%.
        return min(99, 25 + stages_completed * 20)

    @property
    def total_duration_ms(self) -> float:
        """Total elapsed time since job creation in milliseconds."""

        end_time = self.completed_at or datetime.now(timezone.utc)
        return (end_time - self.created_at).total_seconds() * 1000.0

    @property
    def chunks_created(self) -> int:
        """Number of chunks generated for this job."""

        return len(self.chunks)


@dataclass
class IngestionContext:
    """Context object passed through orchestration stages for logging and state.

    This keeps the ingestion identifiers, trace context, and access to the
    job store together, and provides a helper for structured logging.
    """

    ingestion_id: UUID
    document_id: UUID
    trace_context: Optional[Dict[str, Any]]
    job_store: "IngestionJobStore"

    def log(self, stage: str, message: str, **extra: Any) -> None:
        """Emit a structured log entry for a given ingestion stage."""

        from backend.core.logging import get_logger

        logger = get_logger("rag.core.ingestion")
        logger.info(
            message,
            extra={
                "context": {
                    "ingestion_id": str(self.ingestion_id),
                    "document_id": str(self.document_id),
                    "stage": stage,
                    **(extra or {}),
                    **(self.trace_context or {}),
                }
            },
        )
