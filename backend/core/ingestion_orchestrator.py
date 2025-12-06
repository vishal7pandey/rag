from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from backend.api.schemas import DocumentMetadata, IngestionConfig
from backend.core.chunking_models import ChunkingConfig
from backend.core.chunking_service import ChunkingService
from backend.core.ingestion_models import (
    IngestionContext,
    IngestionJob,
    IngestionStatus,
)
from backend.core.ingestion_store import IngestionJobStore
from backend.core.logging import get_logger
from backend.core.text_extraction_service import TextExtractionService


class IngestionOrchestrator:
    """Orchestrates extraction → chunking → embedding for an ingestion job.

    This class wires together existing core services. It is intentionally
    conservative in its assumptions so it can be tested with mocked
    dependencies and evolve as the embedding/storage layers mature.
    """

    def __init__(
        self,
        *,
        extraction_service: Optional[TextExtractionService] = None,
        chunking_service: Optional[ChunkingService] = None,
        embedding_service: Any = None,
        job_store: Optional[IngestionJobStore] = None,
    ) -> None:
        self._extraction_service = extraction_service or TextExtractionService()
        self._chunking_service = chunking_service or ChunkingService()
        # ``embedding_service`` is kept generic here so that this orchestrator
        # can be used even in branches where the embedding layer is not
        # available yet. Tests can pass a MagicMock or simple stub implementing
        # ``embed_and_store``.
        self._embedding_service = embedding_service
        self._job_store = job_store or IngestionJobStore()
        self._logger = get_logger("rag.core.ingestion_orchestrator")

    async def ingest_and_store(
        self,
        job_id: UUID,
        files: List[Tuple[str, bytes]],
        document_metadata: DocumentMetadata,
        ingestion_config: IngestionConfig,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> IngestionJob:
        """Execute extraction → chunking → embedding for a single job.

        The job must already exist in the ``IngestionJobStore``. This method
        updates the job's status, metrics, and pipeline state as it runs.
        """

        trace_context = trace_context or {}

        job = self._job_store.get_job(job_id)
        if job is None:
            raise KeyError(f"Ingestion job {job_id} not found")

        context = IngestionContext(
            ingestion_id=job.ingestion_id,
            document_id=job.document_id,
            trace_context=trace_context,
            job_store=self._job_store,
        )

        # ------------------------------------------------------------------
        # Stage 1: Extraction
        # ------------------------------------------------------------------
        self._job_store.update_status(job_id, IngestionStatus.PROCESSING)
        context.log("extraction", "extraction_started")

        if not files:
            error = "No files provided for ingestion"
            self._job_store.update_status(
                job_id,
                IngestionStatus.FAILED,
                error_message=error,
                error_stage="extraction",
            )
            context.log("extraction", "extraction_failed", error=error)
            return job

        filename, content = files[0]

        try:
            t0 = time.time()
            extracted = self._extraction_service.extract(
                filename=filename,
                content=content,
                document_id=job.document_id,
            )
            extraction_duration_ms = (time.time() - t0) * 1000.0
            job.extracted_document = extracted
            self._job_store.update_metrics(
                job_id,
                "extraction",
                duration_ms=extraction_duration_ms,
                pages=getattr(extracted, "total_pages", 0),
            )
            context.log(
                "extraction",
                "extraction_completed",
                duration_ms=extraction_duration_ms,
            )
        except Exception as exc:  # pragma: no cover - exercised via tests
            error = str(exc)
            self._job_store.update_status(
                job_id,
                IngestionStatus.FAILED,
                error_message=error,
                error_stage="extraction",
            )
            context.log("extraction", "extraction_failed", error=error)
            return job

        # ------------------------------------------------------------------
        # Stage 2: Chunking
        # ------------------------------------------------------------------
        context.log("chunking", "chunking_started")

        try:
            # Map ingestion config (token-based) to a coarse character-based
            # chunking configuration. For now we use a simple multiplier.
            approx_chars_per_token = 4
            chunk_config = ChunkingConfig(
                strategy="recursive",
                chunk_size_chars=ingestion_config.chunk_size_tokens
                * approx_chars_per_token,
                chunk_overlap_chars=ingestion_config.chunk_overlap_tokens
                * approx_chars_per_token,
            )

            t0 = time.time()
            chunk_result = self._chunking_service.chunk_document(
                extracted_document=extracted,
                config=chunk_config,
                trace_context={"ingestion_id": str(job.ingestion_id)},
            )
            chunking_duration_ms = getattr(
                chunk_result, "chunking_duration_ms", (time.time() - t0) * 1000.0
            )
            job.chunks = list(getattr(chunk_result, "chunks", []))

            self._job_store.update_metrics(
                job_id,
                "chunking",
                duration_ms=chunking_duration_ms,
                chunks=len(job.chunks),
            )

            context.log(
                "chunking",
                "chunking_completed",
                duration_ms=chunking_duration_ms,
                chunks=len(job.chunks),
            )
        except Exception as exc:  # pragma: no cover - exercised via tests
            error = str(exc)
            self._job_store.update_status(
                job_id,
                IngestionStatus.FAILED,
                error_message=error,
                error_stage="chunking",
            )
            context.log("chunking", "chunking_failed", error=error)
            return job

        # ------------------------------------------------------------------
        # Stage 3: Embedding (optional in this story)
        # ------------------------------------------------------------------
        if self._embedding_service is not None and job.chunks:
            context.log("embedding", "embedding_started")

            try:
                t0 = time.time()
                embed_result = await self._embedding_service.embed_and_store(
                    job.chunks,
                    ingestion_config,
                    trace_context={"ingestion_id": str(job.ingestion_id)},
                )

                embedding_duration_ms = getattr(
                    embed_result, "embedding_duration_ms", (time.time() - t0) * 1000.0
                )
                job.embeddings = list(getattr(embed_result, "embeddings", []))

                quality_metrics = getattr(embed_result, "quality_metrics", {}) or {}
                self._job_store.update_metrics(
                    job_id,
                    "embedding",
                    duration_ms=embedding_duration_ms,
                    **quality_metrics,
                )

                context.log(
                    "embedding",
                    "embedding_completed",
                    duration_ms=embedding_duration_ms,
                    embeddings=len(job.embeddings),
                )
            except Exception as exc:  # pragma: no cover - exercised via tests
                error = str(exc)
                self._job_store.update_status(
                    job_id,
                    IngestionStatus.FAILED,
                    error_message=error,
                    error_stage="embedding",
                )
                context.log("embedding", "embedding_failed", error=error)
                return job

        # ------------------------------------------------------------------
        # Completed
        # ------------------------------------------------------------------
        self._job_store.update_status(job_id, IngestionStatus.COMPLETED)
        context.log(
            "ingestion",
            "ingestion_completed",
            chunks=len(job.chunks),
            embeddings=len(job.embeddings),
        )

        return job
