from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from backend.core.chunking_models import Chunk
from backend.core.embedding_models import (
    BatchEmbeddingConfig,
    EmbeddingFailure,
    EmbeddingInput,
    EmbeddingResult,
)
from backend.core.embedding_provider import (
    BatchEmbeddingProvider,
    EmbeddingProviderError,
)
from backend.core.embedding_quality import EmbeddingQualityValidator
from backend.core.logging import get_logger
from backend.core.vector_storage import (
    InMemoryVectorDBStorageLayer,
    VectorDBStorageLayer,
)


class EmbeddingService:
    """Main embedding orchestration service.

    This service ties together:

    - ``Chunk`` models produced by the chunking pipeline
    - ``BatchEmbeddingProvider`` for calling the embedding API with retry/backoff
    - ``EmbeddingQualityValidator`` for basic vector sanity checks
    - ``VectorDBStorageLayer`` for persistence (in-memory in this story)
    """

    def __init__(
        self,
        provider: BatchEmbeddingProvider,
        storage: Optional[VectorDBStorageLayer] = None,
    ) -> None:
        self._provider = provider
        self._storage = storage or InMemoryVectorDBStorageLayer()
        self._logger = get_logger("rag.core.embedding_service")

    async def embed_and_store(
        self,
        chunks: List[Chunk],
        config: BatchEmbeddingConfig,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> EmbeddingResult:
        """Embed the given chunks and store resulting embeddings.

        Returns an ``EmbeddingResult`` capturing counts, timings, and metrics.
        """

        trace_context = trace_context or {}
        logger = self._logger

        total_inputs = len(chunks)
        if total_inputs == 0:
            return EmbeddingResult(
                total_inputs=0,
                total_batches=0,
                successful_embeddings=0,
                failed_embeddings=0,
                total_api_calls=0,
                total_retries=0,
                embeddings=[],
                failures=[],
                embedding_duration_ms=0.0,
                storage_duration_ms=0.0,
                total_duration_ms=0.0,
                quality_metrics={},
            )

        logger.info(
            "embedding_started",
            extra={
                "context": {
                    "total_inputs": total_inputs,
                    "model": config.model,
                    "trace_context": trace_context,
                }
            },
        )

        t_start_total = time.time()

        # Build EmbeddingInput objects, optionally skipping duplicates.
        inputs: List[EmbeddingInput] = []
        duplicates_skipped = 0
        tokens_used_estimate = 0

        for chunk in chunks:
            if config.skip_duplicate_content:
                existing = await self._storage.check_duplicate_content(chunk.content)
                if existing is not None:
                    # Mark duplicate for downstream tracking.
                    chunk.is_duplicate = True
                    duplicates_skipped += 1
                    continue

            tokens_used_estimate += chunk.token_count

            inputs.append(
                EmbeddingInput(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    metadata=chunk.metadata,
                    token_count=chunk.token_count,
                    quality_score=chunk.quality_score,
                )
            )

        if not inputs:
            duration_total_ms = (time.time() - t_start_total) * 1000.0
            return EmbeddingResult(
                total_inputs=total_inputs,
                total_batches=0,
                successful_embeddings=0,
                failed_embeddings=0,
                total_api_calls=0,
                total_retries=0,
                embeddings=[],
                failures=[],
                embedding_duration_ms=0.0,
                storage_duration_ms=0.0,
                total_duration_ms=duration_total_ms,
                quality_metrics={
                    "tokens_used_estimate": tokens_used_estimate,
                    "duplicates_skipped": duplicates_skipped,
                },
            )

        # Call provider to obtain embeddings.
        t_start_embed = time.time()
        provider_failures: List[EmbeddingFailure] = []
        embeddings_models = []

        try:
            embeddings_models = await self._provider.embed_batch_with_metadata(
                inputs,
                trace_context=trace_context,
            )
        except EmbeddingProviderError as exc:
            # Treat this as a failure for all remaining inputs in this simple
            # implementation; more advanced recovery strategies can be added
            # in later stories.
            for input_item in inputs:
                provider_failures.append(
                    EmbeddingFailure(
                        chunk_id=input_item.chunk_id,
                        error=str(exc),
                        retry_count=0,
                        metadata={"stage": "provider"},
                    )
                )

            embedding_duration_ms = (time.time() - t_start_embed) * 1000.0
            total_duration_ms = (time.time() - t_start_total) * 1000.0

            logger.error(
                "embedding_failed",
                extra={
                    "context": {
                        "error": str(exc),
                        "total_inputs": total_inputs,
                        "trace_context": trace_context,
                    }
                },
            )

            return EmbeddingResult(
                total_inputs=total_inputs,
                total_batches=1,
                successful_embeddings=0,
                failed_embeddings=len(inputs),
                total_api_calls=1,
                total_retries=0,
                embeddings=[],
                failures=provider_failures,
                embedding_duration_ms=embedding_duration_ms,
                storage_duration_ms=0.0,
                total_duration_ms=total_duration_ms,
                quality_metrics={
                    "tokens_used_estimate": tokens_used_estimate,
                    "duplicates_skipped": duplicates_skipped,
                },
            )

        embedding_duration_ms = (time.time() - t_start_embed) * 1000.0

        # Validate embeddings and update per-chunk flags.
        valid_embeddings = []
        for emb in embeddings_models:
            quality = EmbeddingQualityValidator.validate_embedding(
                emb.embedding,
                expected_dimension=config.embedding_dimension,
            )
            emb.embedding_quality_score = float(quality["quality_score"])

            if not quality["is_valid"]:
                provider_failures.append(
                    EmbeddingFailure(
                        chunk_id=emb.chunk_id,
                        error="invalid_embedding",
                        retry_count=0,
                        metadata={"issues": quality["issues"]},
                    )
                )
                continue

            # Mark source chunk as having a valid embedding when possible.
            for chunk in chunks:
                if chunk.chunk_id == emb.chunk_id:
                    chunk.has_valid_embedding = True
                    break

            valid_embeddings.append(emb)

        # Persist embeddings via the storage layer.
        t_start_store = time.time()

        storage_result = await self._storage.store_embeddings_batch(valid_embeddings)

        storage_duration_ms = (time.time() - t_start_store) * 1000.0
        total_duration_ms = (time.time() - t_start_total) * 1000.0

        successful_embeddings = int(storage_result.get("stored_count", 0))
        failed_storage = int(storage_result.get("failed_count", 0))
        failed_embeddings = failed_storage + len(provider_failures)

        avg_embedding_quality = 0.0
        if valid_embeddings:
            avg_embedding_quality = sum(
                emb.embedding_quality_score for emb in valid_embeddings
            ) / float(len(valid_embeddings))

        quality_metrics: Dict[str, Any] = {
            "tokens_used_estimate": tokens_used_estimate,
            "duplicates_skipped": duplicates_skipped,
            "avg_embedding_quality_score": avg_embedding_quality,
            "valid_embeddings": len(valid_embeddings),
        }

        logger.info(
            "embedding_completed",
            extra={
                "context": {
                    "total_inputs": total_inputs,
                    "successful_embeddings": successful_embeddings,
                    "failed_embeddings": failed_embeddings,
                    "duration_ms": total_duration_ms,
                    "trace_context": trace_context,
                }
            },
        )

        return EmbeddingResult(
            total_inputs=total_inputs,
            total_batches=1,
            successful_embeddings=successful_embeddings,
            failed_embeddings=failed_embeddings,
            total_api_calls=1,
            total_retries=0,
            embeddings=valid_embeddings,
            failures=provider_failures,
            embedding_duration_ms=embedding_duration_ms,
            storage_duration_ms=storage_duration_ms,
            total_duration_ms=total_duration_ms,
            quality_metrics=quality_metrics,
        )
