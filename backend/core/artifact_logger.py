from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.config.debug_settings import DebugSettings
from backend.core.artifact_storage import ArtifactStorage
from backend.core.generation_models import QueryGenerationMetadata
from backend.core.logging import get_logger
from backend.core.query_models import RetrievedChunk
from backend.core.tracing import get_trace_context


class ArtifactLogger:
    """Logs intermediate artifacts at each pipeline stage (Story 016).

    When debug logging is disabled via ``DebugSettings.enabled``, all
    ``log_*`` methods return immediately.
    """

    def __init__(self, settings: DebugSettings, storage: ArtifactStorage) -> None:
        self._settings = settings
        self._storage = storage
        self._logger = get_logger("rag.artifacts")

    # ------------------------------------------------------------------
    # Public logging methods
    # ------------------------------------------------------------------

    def log_query_artifact(
        self,
        *,
        query_text: str,
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._settings.enabled:
            return

        tc = trace_context or get_trace_context()
        artifact: Dict[str, Any] = {
            "type": "query",
            "timestamp": _now_iso(),
            "query_text": query_text,
            "query_length": len(query_text),
            "top_k": top_k,
            "filters": filters or {},
            "query_tokens_estimate": _estimate_tokens(query_text),
        }

        self._store_artifact(artifact, tc)

    def log_retrieved_chunks_artifact(
        self,
        *,
        chunks: List[RetrievedChunk],
        retrieval_latency_ms: float,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._settings.enabled:
            return

        tc = trace_context or get_trace_context()
        chunks_data: List[Dict[str, Any]] = []
        for i, chunk in enumerate(chunks):
            chunk_dict: Dict[str, Any] = {
                "rank": i + 1,
                "chunk_id": str(chunk.chunk_id),
                "similarity_score": chunk.similarity_score,
                "metadata": chunk.metadata,
            }

            if self._settings.include_chunk_content:
                content = (chunk.content or "")[
                    : self._settings.max_artifact_size_bytes
                ]
                chunk_dict["content"] = content
                chunk_dict["content_preview"] = content[:200]

            chunks_data.append(chunk_dict)

        if chunks:
            avg_score = sum(c.similarity_score for c in chunks) / float(len(chunks))
        else:
            avg_score = 0.0

        artifact = {
            "type": "retrieved_chunks",
            "timestamp": _now_iso(),
            "chunks_count": len(chunks),
            "chunks_data": chunks_data,
            "retrieval_latency_ms": retrieval_latency_ms,
            "average_similarity_score": avg_score,
        }

        self._store_artifact(artifact, tc)

    def log_prompt_artifact(
        self,
        *,
        system_message: str,
        user_message: str,
        token_breakdown: Dict[str, int],
        citation_map: Dict[str, Any],
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._settings.enabled:
            return

        tc = trace_context or get_trace_context()
        artifact: Dict[str, Any] = {
            "type": "prompt",
            "timestamp": _now_iso(),
            "system_prompt_tokens": token_breakdown.get("system_tokens", 0),
            "context_tokens": token_breakdown.get("context_tokens", 0),
            "response_tokens": token_breakdown.get("response_tokens", 0),
            "total_tokens": sum(token_breakdown.values()),
        }

        if self._settings.include_prompt_details:
            artifact["system_message"] = system_message[
                : self._settings.max_artifact_size_bytes
            ]
            artifact["user_message"] = user_message[
                : self._settings.max_artifact_size_bytes
            ]
            artifact["citation_map"] = citation_map

        self._store_artifact(artifact, tc)

    def log_answer_artifact(
        self,
        *,
        answer_text: str,
        raw_llm_output: Optional[str],
        generation_latency_ms: float,
        model: str,
        token_usage: Dict[str, int],
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._settings.enabled:
            return

        tc = trace_context or get_trace_context()
        artifact: Dict[str, Any] = {
            "type": "answer",
            "timestamp": _now_iso(),
            "answer_text": answer_text[: self._settings.max_artifact_size_bytes],
            "answer_tokens": token_usage.get("answer_tokens", 0),
            "generation_latency_ms": generation_latency_ms,
            "model": model,
            "completion_tokens": token_usage.get("completion_tokens", 0),
            "prompt_tokens": token_usage.get("prompt_tokens", 0),
            "total_tokens": token_usage.get("total_tokens", 0),
        }

        if self._settings.include_llm_raw_output and raw_llm_output:
            artifact["raw_llm_output"] = raw_llm_output[
                : self._settings.max_artifact_size_bytes
            ]

        self._store_artifact(artifact, tc)

    def log_response_artifact(
        self,
        *,
        answer: str,
        citations: List[Dict[str, Any]],
        used_chunks: List[Dict[str, Any]],
        metadata: QueryGenerationMetadata,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._settings.enabled:
            return

        tc = trace_context or get_trace_context()
        artifact: Dict[str, Any] = {
            "type": "response",
            "timestamp": _now_iso(),
            "answer_preview": answer[:200],
            "citations_count": len(citations),
            "used_chunks_count": len(used_chunks),
            "total_latency_ms": metadata.total_latency_ms,
            "model": metadata.model,
            "chunks_retrieved": metadata.chunks_retrieved,
            "metadata": {
                "embedding_latency_ms": metadata.embedding_latency_ms,
                "retrieval_latency_ms": metadata.retrieval_latency_ms,
                "prompt_assembly_latency_ms": metadata.prompt_assembly_latency_ms,
                "generation_latency_ms": metadata.generation_latency_ms,
                "answer_processing_latency_ms": metadata.answer_processing_latency_ms,
            },
        }

        self._store_artifact(artifact, tc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _store_artifact(
        self,
        artifact: Dict[str, Any],
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        trace_ctx = trace_context or get_trace_context()
        trace_id = trace_ctx.get("trace_id") or "unknown"

        # Log to structured logs with a compact, redacted context.
        context: Dict[str, Any] = {
            "artifact_type": artifact.get("type"),
            "trace_id": trace_id,
            "timestamp": artifact.get("timestamp"),
        }

        self._logger.info("artifact_logged", extra={"context": context})

        async def _store() -> None:
            await self._storage.store(
                trace_id=trace_id,
                artifact_type=str(artifact.get("type")),
                artifact_data=artifact,
            )

        # Fire-and-forget when an event loop is running; fall back to a
        # synchronous asyncio.run call in purely synchronous contexts such as
        # unit tests that invoke ArtifactLogger methods directly.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_store())
        else:
            loop.create_task(_store())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _estimate_tokens(text: str) -> int:
    """Very rough token estimate based on whitespace splitting.

    This is intentionally simple to avoid pulling in tokenizer
    dependencies for Story 016.
    """

    if not text:
        return 0
    return len(text.split())
