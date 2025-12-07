from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from backend.core.exceptions import (
    BadRequestError,
    RAGException,
    RateLimitError,
    ServiceUnavailableError,
)
from backend.core.generation_models import (
    CitationEntry,
    QueryGenerationMetadata,
    QueryGenerationRequest,
    QueryGenerationResponse,
    UsedChunk,
)
from backend.core.artifact_logger import ArtifactLogger
from backend.core.guardrails import TimeoutManager
from backend.core.prompt_models import (
    PromptConstructionResponse,
    create_prompt_request,
)
from backend.core.prompt_services import PromptAssembler
from backend.core.query_models import RetrievedChunk, create_query_request
from backend.core.query_services import QueryOrchestrator
from backend.providers.openai_client import OpenAIGenerationClient


class CitationExtractor:
    """Extract [Source N] markers from LLM answer text."""

    _PATTERN = re.compile(r"\[Source (\d+)\]")

    def extract_citations(self, answer_text: str) -> Dict[int, List[Tuple[int, int]]]:
        """Return mapping of source index to list of (start, end) positions."""

        result: Dict[int, List[Tuple[int, int]]] = {}
        if not answer_text:
            return result

        for match in self._PATTERN.finditer(answer_text):
            index_str = match.group(1)
            try:
                index = int(index_str)
            except ValueError:
                continue

            if index <= 0:
                continue

            positions = result.setdefault(index, [])
            positions.append((match.start(), match.end()))

        return result


class CitationValidator:
    """Validate extracted citations against the prompt citation map."""

    def validate(
        self,
        *,
        extracted_citations: Dict[int, List[Tuple[int, int]]],
        citation_map: Dict[int, Dict[str, Any]],
        retrieved_chunks: List[RetrievedChunk],
    ) -> Tuple[List[CitationEntry], List[str]]:
        """Return (valid_citations, warnings)."""

        citations: List[CitationEntry] = []
        warnings: List[str] = []

        chunk_by_id: Dict[UUID, RetrievedChunk] = {
            chunk.chunk_id: chunk for chunk in retrieved_chunks
        }

        for index in sorted(extracted_citations.keys()):
            meta = citation_map.get(index)
            if meta is None:
                warnings.append(f"Missing citation for [Source {index}]")
                continue

            chunk_id_str = meta.get("chunk_id")
            if not chunk_id_str:
                warnings.append(f"Missing chunk_id for [Source {index}]")
                continue

            try:
                chunk_id = UUID(chunk_id_str)
            except Exception:
                warnings.append(f"Invalid chunk_id for [Source {index}]")
                continue

            chunk = chunk_by_id.get(chunk_id)

            similarity = float(
                meta.get("similarity_score", getattr(chunk, "similarity_score", 0.0))
            )

            document_id_val = meta.get("document_id")
            document_id: Optional[UUID]
            if document_id_val:
                try:
                    document_id = UUID(document_id_val)
                except Exception:
                    document_id = None
            else:
                document_id = None

            source_file = meta.get("source_file")
            page_val = meta.get("page")
            page: Optional[int] = page_val if isinstance(page_val, int) else None

            preview = meta.get("preview")
            if not preview and chunk is not None:
                preview = (chunk.content or "")[:150]
            if not preview:
                preview = ""

            citations.append(
                CitationEntry(
                    source_index=index,
                    chunk_id=chunk_id,
                    document_id=document_id,
                    source_file=source_file,
                    page=page,
                    similarity_score=similarity,
                    preview=preview,
                )
            )

        return citations, warnings


class AnswerProcessor:
    """Post-process LLM responses into answer, citations, and used chunks."""

    def __init__(
        self,
        extractor: Optional[CitationExtractor] = None,
        validator: Optional[CitationValidator] = None,
    ) -> None:
        self._extractor = extractor or CitationExtractor()
        self._validator = validator or CitationValidator()

    async def process(
        self,
        llm_response: str,
        citation_map: Dict[int, Dict[str, Any]],
        retrieved_chunks: List[RetrievedChunk],
        prompt_response: Optional[PromptConstructionResponse] = None,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[CitationEntry], List[UsedChunk], List[str]]:
        """Process raw LLM answer text and build citations and used chunks."""

        answer_text = (llm_response or "").strip()

        extracted = self._extractor.extract_citations(answer_text)
        citations, warnings = self._validator.validate(
            extracted_citations=extracted,
            citation_map=citation_map,
            retrieved_chunks=retrieved_chunks,
        )

        # Build UsedChunk list from chunks referenced in the citation_map.
        used_chunks: List[UsedChunk] = []
        chunk_by_id: Dict[UUID, RetrievedChunk] = {
            chunk.chunk_id: chunk for chunk in retrieved_chunks
        }

        seen_chunk_ids: set[UUID] = set()
        for index in sorted(citation_map.keys()):
            meta = citation_map[index]
            chunk_id_str = meta.get("chunk_id")
            if not chunk_id_str:
                continue

            try:
                chunk_id = UUID(chunk_id_str)
            except Exception:
                continue

            if chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk_id)

            chunk = chunk_by_id.get(chunk_id)
            if chunk is not None:
                preview = (chunk.content or "")[:100]
                rank = chunk.rank
                similarity = chunk.similarity_score
            else:
                preview = str(meta.get("preview") or "")[:100]
                rank = 0
                similarity = float(meta.get("similarity_score", 0.0))

            used_chunks.append(
                UsedChunk(
                    chunk_id=chunk_id,
                    rank=rank,
                    similarity_score=similarity,
                    content_preview=preview,
                )
            )

        return answer_text, citations, used_chunks, warnings


class GenerationErrorMapper:
    """Map generation/provider errors to HTTP-friendly status and messages.

    This is a small adapter that converts exceptions raised during generation
    into a tuple suitable for HTTP error responses:

    (status_code, error_type, user_message)
    """

    def map_error(self, error: Exception) -> Tuple[int, str, str]:
        """Map an exception to (status_code, error_type, user_message)."""

        # Rate limit semantics: surface as temporary unavailability.
        if isinstance(error, RateLimitError):
            return (
                503,
                "rate_limit",
                "The answer generation service is temporarily unavailable due to rate limiting. "
                "Please try again in a little while.",
            )

        # Explicit service-unavailable conditions.
        if isinstance(error, ServiceUnavailableError):
            return (
                503,
                "service_unavailable",
                "The answer generation service is temporarily unavailable. Please try again later.",
            )

        # Bad request or validation-like errors.
        if isinstance(error, BadRequestError) or isinstance(error, ValueError):
            return (
                400,
                "invalid_request",
                "Your request could not be processed. Please check the query and try again.",
            )

        # Generic RAG exceptions preserve their status code and error code.
        if isinstance(error, RAGException):
            return (
                error.status_code,
                error.error_code,
                "The service encountered an error while generating an answer.",
            )

        # Fallback: treat as provider error.
        return (
            503,
            "provider_error",
            "The answer generation provider is temporarily unavailable. Please try again later.",
        )


class GenerationOrchestrator:
    """Coordinate embed → retrieve → prompt → generate → answer pipeline."""

    def __init__(
        self,
        query_orchestrator: QueryOrchestrator,
        prompt_assembler: Optional[PromptAssembler] = None,
        generation_client: Optional[OpenAIGenerationClient] = None,
        answer_processor: Optional[AnswerProcessor] = None,
        error_mapper: Optional[GenerationErrorMapper] = None,
    ) -> None:
        self._query_orchestrator = query_orchestrator
        self._prompt_assembler = prompt_assembler or PromptAssembler()
        self._generation_client = generation_client or OpenAIGenerationClient()
        self._answer_processor = answer_processor or AnswerProcessor()
        self._error_mapper = error_mapper or GenerationErrorMapper()

    async def generate_answer(
        self,
        query_request: QueryGenerationRequest,
        trace_context: Optional[Dict[str, Any]] = None,
        timeout_manager: Optional[TimeoutManager] = None,
        artifact_logger: Optional[ArtifactLogger] = None,
    ) -> QueryGenerationResponse:
        """Execute the full generation pipeline for a query.

        This method intentionally raises exceptions (EmbeddingProviderError,
        RAGException, or provider errors). The API layer is responsible for
        mapping them to HTTP responses using the existing error handler and the
        GenerationErrorMapper when appropriate.
        """
        trace_context = trace_context or {}
        timeout_manager = timeout_manager or TimeoutManager()

        # Stage 1: retrieval via QueryOrchestrator.
        timeout_manager.assert_time_available(
            min_required_seconds=1.0,
            stage_name="stage_1_retrieval",
            stages_completed=0,
        )
        internal_query_request = create_query_request(
            query_text=query_request.query,
            top_k=query_request.top_k,
            search_type="dense",
            filters=query_request.filters or {},
            include_metadata=query_request.include_sources,
            trace_context=trace_context,
        )

        query_response = await self._query_orchestrator.query(internal_query_request)

        if artifact_logger is not None:
            metrics_internal_stage1 = query_response.metrics or {}
            retrieval_latency_stage1 = float(
                metrics_internal_stage1.get("retrieval_latency_ms", 0.0)
            )
            artifact_logger.log_retrieved_chunks_artifact(
                chunks=query_response.retrieved_chunks,
                retrieval_latency_ms=retrieval_latency_stage1,
                trace_context=trace_context,
            )

        # Stage 2: prompt construction via PromptAssembler.
        timeout_manager.assert_time_available(
            min_required_seconds=1.0,
            stage_name="stage_2_prompt_construction",
            stages_completed=1,
        )
        prompt_request = create_prompt_request(
            query_text=query_request.query,
            retrieved_chunks=query_response.retrieved_chunks,
            model="gpt-5-nano",
            max_tokens_for_response=1500,
            include_sources=query_request.include_sources,
            trace_context=trace_context,
        )

        prompt_response = self._prompt_assembler.construct_prompt(prompt_request)

        if artifact_logger is not None:
            token_breakdown = prompt_response.token_metrics or {}
            artifact_logger.log_prompt_artifact(
                system_message=prompt_response.system_message,
                user_message=prompt_response.user_message,
                token_breakdown=token_breakdown,
                citation_map=prompt_response.citation_map,
                trace_context=trace_context,
            )

        # Stage 3: LLM generation via OpenAIGenerationClient.
        timeout_manager.assert_time_available(
            min_required_seconds=1.0,
            stage_name="stage_3_generation",
            stages_completed=2,
        )
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": prompt_response.system_message},
            {"role": "user", "content": prompt_response.user_message},
        ]

        generation_result = self._generation_client.generate(
            messages=messages,
            max_tokens=prompt_request.max_tokens_for_response,
            stream=False,
        )

        answer_text_raw: str = str(generation_result.get("content") or "")

        if artifact_logger is not None:
            usage_for_answer = generation_result.get("usage") or {}
            token_usage = {
                "answer_tokens": int(usage_for_answer.get("completion_tokens", 0)),
                "prompt_tokens": int(usage_for_answer.get("prompt_tokens", 0)),
                "total_tokens": int(usage_for_answer.get("total_tokens", 0)),
            }
            generation_latency_raw = float(generation_result.get("latency_ms", 0.0))
            artifact_logger.log_answer_artifact(
                answer_text=answer_text_raw,
                raw_llm_output=str(generation_result),
                generation_latency_ms=generation_latency_raw,
                model=str(generation_result.get("model") or "unknown"),
                token_usage=token_usage,
                trace_context=trace_context,
            )

        # Stage 4: answer post-processing.
        timeout_manager.assert_time_available(
            min_required_seconds=1.0,
            stage_name="stage_4_answer_processing",
            stages_completed=3,
        )
        start_answer_processing = time.time()
        (
            answer_text,
            citations,
            used_chunks,
            warnings,
        ) = await self._answer_processor.process(
            llm_response=answer_text_raw,
            citation_map=prompt_response.citation_map,
            retrieved_chunks=query_response.retrieved_chunks,
            prompt_response=prompt_response,
            trace_context=trace_context,
        )
        answer_processing_latency_ms = (time.time() - start_answer_processing) * 1000.0

        # Metrics aggregation.
        metrics_internal = query_response.metrics

        embedding_latency_ms = float(metrics_internal.get("embedding_latency_ms", 0.0))
        retrieval_latency_ms = float(metrics_internal.get("retrieval_latency_ms", 0.0))
        prompt_assembly_latency_ms = float(prompt_response.assembly_latency_ms)
        generation_latency_ms = float(generation_result.get("latency_ms", 0.0))
        # Log per-stage timings using the timeout manager helper.
        stage_1_latency = embedding_latency_ms + retrieval_latency_ms
        timeout_manager.log_stage_timing("stage_1_retrieval", stage_1_latency)
        timeout_manager.log_stage_timing(
            "stage_2_prompt_construction", prompt_assembly_latency_ms
        )
        timeout_manager.log_stage_timing("stage_3_generation", generation_latency_ms)
        timeout_manager.log_stage_timing(
            "stage_4_answer_processing", answer_processing_latency_ms
        )
        total_latency_ms = timeout_manager.get_elapsed_ms()

        usage = generation_result.get("usage") or {}
        total_tokens_used = int(usage.get("total_tokens", 0))

        metadata = QueryGenerationMetadata(
            total_latency_ms=total_latency_ms,
            embedding_latency_ms=embedding_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            prompt_assembly_latency_ms=prompt_assembly_latency_ms,
            generation_latency_ms=generation_latency_ms,
            answer_processing_latency_ms=answer_processing_latency_ms,
            total_tokens_used=total_tokens_used,
            model=str(generation_result.get("model") or "unknown"),
            chunks_retrieved=len(query_response.retrieved_chunks),
        )

        if artifact_logger is not None:
            artifact_logger.log_response_artifact(
                answer=answer_text,
                citations=citations,
                used_chunks=used_chunks,
                metadata=metadata,
                trace_context=trace_context,
            )

        # Currently, warnings from AnswerProcessor are not surfaced separately in
        # QueryGenerationResponse; they can be logged by the caller if needed.

        return QueryGenerationResponse(
            query_id=query_response.query_id,
            answer=answer_text,
            citations=citations,
            used_chunks=used_chunks,
            metadata=metadata,
        )
