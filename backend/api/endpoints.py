"""API route handlers for the backend service.

This module defines the HTTP endpoints for health checks, ingestion, and query
operations. Business logic is stubbed for now and will be implemented in
later stories.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from os import getenv
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Request, status

from backend.api.errors import (
    ServiceUnavailableError,
    to_http_exception,
)
from backend.api.schemas import (
    Chunk,
    DocumentMetadata,
    HealthResponse,
    HealthStatus,
    IngestionConfig,
    IngestionResponse,
    IngestionStatus,
    QueryRequest,
    QueryResponse,
    RetrievalChunk,
    RetrievalMetrics,
    RetrievalRequest,
    RetrievalResponse,
    UploadedFileInfo,
)
from backend.config.settings import settings
from backend.config.debug_settings import DebugSettings
from backend.core.generation_models import QueryGenerationRequest
from backend.core.generation_services import (
    GenerationErrorMapper,
    GenerationOrchestrator,
)
from backend.core.artifact_logger import ArtifactLogger
from backend.core.artifact_storage import (
    InMemoryArtifactStorage,
    PostgresArtifactStorage,
)
from backend.core.guardrails import InputValidator, TimeoutManager
from backend.core.exceptions import (
    FileValidationError,
    QueryTimeoutError,
    RateLimitError,
)
from backend.core.file_validator import FileValidator
from backend.core.embedding_provider import EmbeddingProviderError
from backend.core.ingestion_orchestrator import IngestionOrchestrator
from backend.core.ingestion_store import IngestionJobStore
from backend.core.query_cache import QueryEmbeddingCache
from backend.core.query_models import create_query_request
from backend.core.query_services import (
    QueryEmbeddingService,
    QueryOrchestrator,
    RetrieverService,
)
from backend.core.rate_limiter import RateLimiter
from backend.core.vector_storage import InMemoryVectorDBStorageLayer
from backend.core.logging import get_logger


router = APIRouter()
logger = get_logger("rag.api.endpoints")


# In-memory store for ingestion status (stub implementation for Story 006).
_INGESTION_STORE: Dict[UUID, IngestionResponse] = {}

# Simple in-memory rate limiter instance for uploads.
_RATE_LIMITER = RateLimiter()

# Ingestion orchestration components for Story 010.
_INGESTION_JOB_STORE = IngestionJobStore()
_INGESTION_ORCHESTRATOR = IngestionOrchestrator(
    extraction_service=None,
    chunking_service=None,
    embedding_service=None,
    job_store=_INGESTION_JOB_STORE,
)

# Query orchestration components for Story 011 / 012.
_VECTOR_STORAGE = InMemoryVectorDBStorageLayer()
_QUERY_EMBEDDING_SERVICE = QueryEmbeddingService()
_QUERY_EMBEDDING_CACHE = QueryEmbeddingCache()
_RETRIEVER_SERVICE = RetrieverService(storage=_VECTOR_STORAGE)
_QUERY_ORCHESTRATOR = QueryOrchestrator(
    embedding_service=_QUERY_EMBEDDING_SERVICE,
    retriever_service=_RETRIEVER_SERVICE,
    embedding_cache=_QUERY_EMBEDDING_CACHE,
)

# Basic input validator for Story 015 guardrails.
_INPUT_VALIDATOR = InputValidator()

# Debug configuration and artifact logging components for Story 016.
_DEBUG_SETTINGS = DebugSettings.from_env()
if getenv("DATABASE_URL"):
    try:
        _ARTIFACT_STORAGE = PostgresArtifactStorage()
    except Exception:  # pragma: no cover - falls back to in-memory storage
        _ARTIFACT_STORAGE = InMemoryArtifactStorage()
else:
    _ARTIFACT_STORAGE = InMemoryArtifactStorage()

_ARTIFACT_LOGGER = ArtifactLogger(_DEBUG_SETTINGS, _ARTIFACT_STORAGE)

# Optional generation orchestrator (Story 014).
#
# In production, when OPENAI_API_KEY is configured, we initialize a real
# GenerationOrchestrator that wires together QueryOrchestrator, PromptAssembler,
# and OpenAIGenerationClient. Tests and non-configured environments can still
# override or disable this by monkeypatching _GENERATION_ORCHESTRATOR.
_GENERATION_ERROR_MAPPER = GenerationErrorMapper()
_GENERATION_ORCHESTRATOR: Optional[GenerationOrchestrator]
if getenv("OPENAI_API_KEY"):
    _GENERATION_ORCHESTRATOR = GenerationOrchestrator(
        query_orchestrator=_QUERY_ORCHESTRATOR
    )
else:  # pragma: no cover - exercised indirectly via tests
    _GENERATION_ORCHESTRATOR = None


def _evaluate_dependencies() -> Dict[str, str]:
    """Return status of external dependencies.

    For now this is stubbed; future stories will perform real checks against
    vector DB, embedding service, etc.
    """

    return {
        "vector_db": "ok",
        "embedding_service": "ok",
    }


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Return basic health information for the service.

    Returns 200 when all dependencies are healthy or degraded, and 503 when
    any dependency is unavailable, matching the Story 002 specification.
    """

    dependencies = _evaluate_dependencies()

    if any(status == "unavailable" for status in dependencies.values()):
        logger.error(
            "Health check failed: one or more dependencies unavailable",
            extra={"dependencies": dependencies},
        )
        raise to_http_exception(ServiceUnavailableError())

    overall_status = HealthStatus.HEALTHY
    if any(status == "degraded" for status in dependencies.values()):
        overall_status = HealthStatus.DEGRADED

    logger.info(
        "Health check",
        extra={
            "status": overall_status.value,
            "environment": settings.ENVIRONMENT,
            "dependencies": dependencies,
        },
    )

    return HealthResponse(
        status=overall_status,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        dependencies=dependencies,
    )


@router.post(
    "/api/ingest/upload",
    response_model=IngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Ingestion"],
)
async def ingest_upload(
    files: Optional[List[UploadFile]] = File(None),
    document_metadata: Optional[str] = Form(None),
    ingestion_config: Optional[str] = Form(None),
) -> IngestionResponse:
    """Accept document upload and return an ingestion_id.

    In addition to files, this endpoint accepts optional JSON-encoded
    `document_metadata` and `ingestion_config` fields as described in
    Story 002 / Story 006. These are validated and logged but not yet
    persisted beyond an in-memory ingestion status store.
    """

    if not files:
        # Use the shared FileValidationError so the global error handler
        # can return a standardized JSON error envelope.
        raise FileValidationError(message="No files provided", validation_errors=[])

    # Basic per-user rate limiting (files per hour, approximated by
    # requests per hour with this simple in-memory limiter).
    from backend.core.tracing import get_trace_context

    trace_ctx = get_trace_context()
    user_id = trace_ctx.get("user_id") or "anonymous"

    is_allowed, retry_after = _RATE_LIMITER.is_allowed(
        user_id=user_id,
        limit=100,
        window_seconds=3600,
    )
    if not is_allowed:
        raise RateLimitError(
            message="Maximum 100 uploads per hour exceeded",
            retry_after_seconds=retry_after or 0,
            details={"user_id": user_id, "limit": 100, "period": "1 hour"},
        )

    metadata_model: Optional[DocumentMetadata] = None
    config_model: Optional[IngestionConfig] = None

    if document_metadata is not None:
        try:
            metadata_model = DocumentMetadata(**json.loads(document_metadata))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Invalid document_metadata payload", exc_info=exc)
            raise FileValidationError(
                message="Invalid document_metadata JSON",
                validation_errors=[
                    {
                        "field": "document_metadata",
                        "error": "Must be valid JSON or schema",
                    }
                ],
            ) from exc

    if ingestion_config is not None:
        try:
            config_model = IngestionConfig(**json.loads(ingestion_config))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Invalid ingestion_config payload", exc_info=exc)
            raise FileValidationError(
                message="Invalid ingestion_config JSON",
                validation_errors=[
                    {
                        "field": "ingestion_config",
                        "error": "Must be valid JSON or schema",
                    }
                ],
            ) from exc

    # Read file contents for validation.
    file_tuples: List[tuple[str, bytes]] = []
    for file in files or []:
        content = await file.read()
        file_tuples.append((file.filename, content))

    validator = FileValidator()
    validation_results, batch_error = validator.validate_batch(file_tuples)

    if batch_error:
        validation_errors = [
            {"filename": r.filename, "error": r.error or "Unknown error"}
            for r in validation_results
            if not r.is_valid
        ]
        raise FileValidationError(
            message=batch_error, validation_errors=validation_errors
        )

    ingestion_id = uuid4()
    document_id = uuid4()

    uploaded_files: List[UploadedFileInfo] = [
        UploadedFileInfo(
            filename=r.filename,
            file_size_mb=r.file_size_mb,
            mime_type=r.mime_type,
        )
        for r in validation_results
        if r.is_valid
    ]

    # Note: real implementation will persist status and enqueue background work.
    resp = IngestionResponse(
        ingestion_id=ingestion_id,
        status=IngestionStatus.PENDING,
        document_id=document_id,
        files=uploaded_files,
    )
    _INGESTION_STORE[ingestion_id] = resp

    logger.info(
        "Ingestion upload accepted",
        extra={
            "ingestion_id": str(ingestion_id),
            "file_count": len(uploaded_files),
            "has_metadata": metadata_model is not None,
            "has_config": config_model is not None,
        },
    )

    return resp


@router.get(
    "/api/ingest/status/{ingestion_id}",
    response_model=IngestionResponse,
    tags=["Ingestion"],
)
async def ingest_status(ingestion_id: UUID) -> IngestionResponse:
    """Return current ingestion status for the given ingestion_id (stubbed)."""

    resp = _INGESTION_STORE.get(ingestion_id)
    if resp is None:
        raise HTTPException(status_code=404, detail="Ingestion not found")
    logger.info(
        "Ingestion status requested",
        extra={"ingestion_id": str(ingestion_id), "status": resp.status.value},
    )
    return resp


@router.post(
    "/ingest",
    response_model=IngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Ingestion"],
)
async def ingest(
    files: Optional[List[UploadFile]] = File(None),
    document_metadata: Optional[str] = Form(None),
    ingestion_config: Optional[str] = Form(None),
) -> IngestionResponse:
    """Orchestrated ingestion endpoint.

    This endpoint reuses the same validation logic as ``/api/ingest/upload`` but
    also runs the extraction → chunking → embedding orchestration synchronously
    using the core ingestion orchestrator.
    """

    if not files:
        raise FileValidationError(message="No files provided", validation_errors=[])

    from backend.core.tracing import get_trace_context

    trace_ctx = get_trace_context()
    user_id = trace_ctx.get("user_id") or "anonymous"

    is_allowed, retry_after = _RATE_LIMITER.is_allowed(
        user_id=user_id,
        limit=100,
        window_seconds=3600,
    )
    if not is_allowed:
        raise RateLimitError(
            message="Maximum 100 uploads per hour exceeded",
            retry_after_seconds=retry_after or 0,
            details={"user_id": user_id, "limit": 100, "period": "1 hour"},
        )

    metadata_model: Optional[DocumentMetadata] = None
    config_model: Optional[IngestionConfig] = None

    if document_metadata is not None:
        try:
            metadata_model = DocumentMetadata(**json.loads(document_metadata))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Invalid document_metadata payload", exc_info=exc)
            raise FileValidationError(
                message="Invalid document_metadata JSON",
                validation_errors=[
                    {
                        "field": "document_metadata",
                        "error": "Must be valid JSON or schema",
                    }
                ],
            ) from exc

    if ingestion_config is not None:
        try:
            config_model = IngestionConfig(**json.loads(ingestion_config))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Invalid ingestion_config payload", exc_info=exc)
            raise FileValidationError(
                message="Invalid ingestion_config JSON",
                validation_errors=[
                    {
                        "field": "ingestion_config",
                        "error": "Must be valid JSON or schema",
                    }
                ],
            ) from exc

    # Read file contents for validation and orchestration.
    file_tuples: List[tuple[str, bytes]] = []
    for file in files or []:
        content = await file.read()
        file_tuples.append((file.filename, content))

    validator = FileValidator()
    validation_results, batch_error = validator.validate_batch(file_tuples)

    if batch_error:
        validation_errors = [
            {"filename": r.filename, "error": r.error or "Unknown error"}
            for r in validation_results
            if not r.is_valid
        ]
        raise FileValidationError(
            message=batch_error, validation_errors=validation_errors
        )

    ingestion_id = uuid4()
    document_id = uuid4()

    uploaded_files: List[UploadedFileInfo] = [
        UploadedFileInfo(
            filename=r.filename,
            file_size_mb=r.file_size_mb,
            mime_type=r.mime_type,
        )
        for r in validation_results
        if r.is_valid
    ]

    # Create an IngestionJob in the core job store.
    job = _INGESTION_JOB_STORE.create_job(
        ingestion_id=ingestion_id,
        document_id=document_id,
        files=uploaded_files,
    )

    # Run the orchestration synchronously for this story.
    await _INGESTION_ORCHESTRATOR.ingest_and_store(
        job_id=job.ingestion_id,
        files=file_tuples,
        document_metadata=metadata_model or DocumentMetadata(),
        ingestion_config=config_model or IngestionConfig(),
        trace_context=trace_ctx,
    )

    # Reload the job to reflect final state.
    final_job = _INGESTION_JOB_STORE.get_job(ingestion_id) or job

    logger.info(
        "Ingestion orchestrated",
        extra={
            "ingestion_id": str(ingestion_id),
            "status": final_job.status.value,
            "chunks_created": final_job.chunks_created,
        },
    )

    return IngestionResponse(
        ingestion_id=final_job.ingestion_id,
        status=IngestionStatus(final_job.status.value),
        document_id=final_job.document_id,
        files=uploaded_files,
        chunks_created=final_job.chunks_created,
        progress_percent=final_job.progress_percent,
        error_message=final_job.error_message,
        created_at=final_job.created_at,
    )


@router.get(
    "/ingest/status/{ingestion_id}",
    response_model=IngestionResponse,
    tags=["Ingestion"],
)
async def ingest_status_orchestrated(ingestion_id: UUID) -> IngestionResponse:
    """Return current orchestrated ingestion status for the given ingestion_id."""

    job = _INGESTION_JOB_STORE.get_job(ingestion_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion not found")

    logger.info(
        "Ingestion status (orchestrated) requested",
        extra={"ingestion_id": str(ingestion_id), "status": job.status.value},
    )

    return IngestionResponse(
        ingestion_id=job.ingestion_id,
        status=IngestionStatus(job.status.value),
        document_id=job.document_id,
        files=job.files,
        chunks_created=job.chunks_created,
        progress_percent=job.progress_percent,
        error_message=job.error_message,
        created_at=job.created_at,
    )


@router.post("/api/query", response_model=QueryResponse, tags=["Query"])
async def query_endpoint(payload: QueryRequest) -> QueryResponse:
    """Execute dense similarity search for a query.

    This implementation wires the core query orchestrator (Story 011) into the
    existing `/api/query` endpoint. When the query embedding service is not
    configured, it falls back to the original "no documents" stub behavior.
    """

    from backend.core.tracing import get_trace_context

    trace_ctx = get_trace_context()

    # Basic input validation before running the RAG pipeline.
    _INPUT_VALIDATOR.validate_request(
        query=payload.query,
        top_k=payload.top_k,
        trace_context=trace_ctx,
    )

    # Global timeout manager for the full RAG pipeline, configured via settings.
    timeout_manager = TimeoutManager(timeout_seconds=settings.QUERY_TIMEOUT_SECONDS)

    # Debug artifact logging: query-level artifact.
    if _DEBUG_SETTINGS.enabled:
        _ARTIFACT_LOGGER.log_query_artifact(
            query_text=payload.query,
            top_k=payload.top_k,
            filters=payload.filters or {},
            trace_context=trace_ctx,
        )

    logger.info(
        "Query endpoint called",
        extra={"query_preview": payload.query[:100], "top_k": payload.top_k},
    )

    # If no generation orchestrator is configured, reuse the original
    # retrieval-only implementation: run the query orchestrator, build
    # retrieved_chunks and citations, and return a snippet-based answer.
    if _GENERATION_ORCHESTRATOR is None:
        internal_request = create_query_request(
            query_text=payload.query,
            top_k=payload.top_k,
            search_type="dense",
            filters=payload.filters or {},
            include_metadata=payload.include_sources,
            trace_context=trace_ctx,
        )

        try:
            internal_response = await _QUERY_ORCHESTRATOR.query(internal_request)
        except EmbeddingProviderError:
            answer = "I have no documents in my knowledge base yet. Please upload documents first."
            return QueryResponse(
                query_id=uuid4(),
                answer=answer,
                citations=[],
                retrieved_chunks=[],
                used_chunks=[],
                latency_ms=50.0,
                confidence_score=None,
                metadata=None,
            )

        include_sources = payload.include_sources
        retrieved_chunks_api: List[Chunk] = []
        citations: List[Dict[str, Any]] = []

        for rc in internal_response.retrieved_chunks:
            if rc.document_id is None:
                continue

            metadata = rc.metadata if include_sources else {}

            retrieved_chunks_api.append(
                Chunk(
                    id=rc.chunk_id,
                    document_id=rc.document_id,
                    chunk_index=max(rc.rank - 1, 0),
                    content=rc.content,
                    dense_embedding=rc.embedding or [],
                    sparse_embedding={},
                    metadata=metadata,
                    quality_score=rc.quality_score,
                    embedding_model=rc.embedding_model or "text-embedding-3-small",
                    created_at=rc.created_at or datetime.now(timezone.utc),
                    updated_at=rc.updated_at or datetime.now(timezone.utc),
                )
            )

            if include_sources:
                citations.append(
                    {
                        "chunk_id": str(rc.chunk_id),
                        "document_id": str(rc.document_id),
                        "rank": rc.rank,
                        "similarity_score": rc.similarity_score,
                        "source": rc.metadata.get("source"),
                        "metadata": rc.metadata,
                    }
                )

        if not retrieved_chunks_api:
            answer = "I have no documents in my knowledge base yet. Please upload documents first."
            citations = []
        else:
            top_snippet = retrieved_chunks_api[0].content.strip().replace("\n", " ")
            if len(top_snippet) > 200:
                top_snippet = top_snippet[:197] + "..."
            answer = (
                "Retrieved relevant context for your query from the knowledge base. "
                "Here is a representative snippet: " + top_snippet
            )

        return QueryResponse(
            query_id=internal_response.query_id,
            answer=answer,
            citations=citations,
            retrieved_chunks=retrieved_chunks_api,
            used_chunks=[],
            latency_ms=internal_response.total_latency_ms,
            confidence_score=None,
            metadata=None,
        )

    # Stage 1: run the generation orchestrator (embed → retrieve → prompt → generate → answer).
    gen_request = QueryGenerationRequest(
        query=payload.query,
        top_k=payload.top_k,
        filters=payload.filters or {},
        include_sources=payload.include_sources,
    )

    try:
        gen_response = await _GENERATION_ORCHESTRATOR.generate_answer(
            gen_request,
            trace_context=trace_ctx,
            timeout_manager=timeout_manager,
            artifact_logger=_ARTIFACT_LOGGER if _DEBUG_SETTINGS.enabled else None,
        )
    except EmbeddingProviderError:
        # Embedding provider not configured yet; preserve original stub behavior.
        answer = "I have no documents in my knowledge base yet. Please upload documents first."
        return QueryResponse(
            query_id=uuid4(),
            answer=answer,
            citations=[],
            retrieved_chunks=[],
            used_chunks=[],
            latency_ms=50.0,
            confidence_score=None,
            metadata=None,
        )
    except QueryTimeoutError as exc:
        # Let the global error handler convert this to a 408 response with the
        # standardized error envelope, instead of remapping via
        # GenerationErrorMapper.
        raise exc
    except Exception as exc:  # noqa: BLE001
        status_code, error_type, message = _GENERATION_ERROR_MAPPER.map_error(exc)
        raise HTTPException(
            status_code=status_code,
            detail={"error": {"type": error_type, "message": message}},
        ) from exc

    # Stage 2: run the retrieval orchestrator to build the retrieved_chunks view
    # exposed by the public API. This reuses the same query params and respects
    # filters and include_sources.
    internal_request = create_query_request(
        query_text=payload.query,
        top_k=payload.top_k,
        search_type="dense",
        filters=payload.filters or {},
        include_metadata=payload.include_sources,
        trace_context=trace_ctx,
    )

    try:
        internal_response = await _QUERY_ORCHESTRATOR.query(internal_request)
    except EmbeddingProviderError:
        # If retrieval fails here, fall back to the same stub behavior.
        answer = "I have no documents in my knowledge base yet. Please upload documents first."
        return QueryResponse(
            query_id=uuid4(),
            answer=answer,
            citations=[],
            retrieved_chunks=[],
            used_chunks=[],
            latency_ms=50.0,
            confidence_score=None,
            metadata=None,
        )

    include_sources = payload.include_sources
    retrieved_chunks_api: List[Chunk] = []

    for rc in internal_response.retrieved_chunks:
        if rc.document_id is None:
            continue

        metadata = rc.metadata if include_sources else {}

        retrieved_chunks_api.append(
            Chunk(
                id=rc.chunk_id,
                document_id=rc.document_id,
                chunk_index=max(rc.rank - 1, 0),
                content=rc.content,
                dense_embedding=rc.embedding or [],
                sparse_embedding={},
                metadata=metadata,
                quality_score=rc.quality_score,
                embedding_model=rc.embedding_model or "text-embedding-3-small",
                created_at=rc.created_at or datetime.now(timezone.utc),
                updated_at=rc.updated_at or datetime.now(timezone.utc),
            )
        )

    # Build citations and used_chunks from the generation response. These are
    # aligned with the prompt-level citation map produced by Story 013.
    citations_api: List[Dict[str, Any]] = []
    used_chunks_api: List[Dict[str, Any]] = []

    for entry in gen_response.citations:
        citations_api.append(
            {
                "source_index": entry.source_index,
                "chunk_id": str(entry.chunk_id),
                "document_id": str(entry.document_id) if entry.document_id else None,
                "source_file": entry.source_file,
                "page": entry.page,
                "similarity_score": entry.similarity_score,
                "preview": entry.preview,
            }
        )

    for uc in gen_response.used_chunks:
        used_chunks_api.append(
            {
                "chunk_id": str(uc.chunk_id),
                "rank": uc.rank,
                "similarity_score": uc.similarity_score,
                "content_preview": uc.content_preview,
            }
        )

    # Build metadata payload from the generation metadata.
    meta = gen_response.metadata
    metadata_api: Dict[str, Any] = {
        "total_latency_ms": meta.total_latency_ms,
        "embedding_latency_ms": meta.embedding_latency_ms,
        "retrieval_latency_ms": meta.retrieval_latency_ms,
        "prompt_assembly_latency_ms": meta.prompt_assembly_latency_ms,
        "generation_latency_ms": meta.generation_latency_ms,
        "total_tokens_used": meta.total_tokens_used,
        "model": meta.model,
        "chunks_retrieved": meta.chunks_retrieved,
    }

    # When no documents are available even though generation succeeded, return
    # the same friendly stubbed answer for consistency with earlier stories.
    if not retrieved_chunks_api:
        answer = "I have no documents in my knowledge base yet. Please upload documents first."
        citations_api = []
        used_chunks_api = []
    else:
        answer = gen_response.answer

    # Respect include_sources=False semantics: hide metadata and citations from
    # the response, but still return an answer.
    if not include_sources:
        for chunk in retrieved_chunks_api:
            chunk.metadata = {}
        citations_api = []

    return QueryResponse(
        query_id=gen_response.query_id,
        answer=answer,
        citations=citations_api,
        retrieved_chunks=retrieved_chunks_api,
        used_chunks=used_chunks_api,
        latency_ms=float(metadata_api["total_latency_ms"]),
        confidence_score=None,
        metadata=metadata_api,
    )


@router.get("/api/debug/artifacts", tags=["Debug"])
async def debug_artifacts(trace_id: str, request: Request) -> Dict[str, Any]:
    """Return stored debug artifacts for the given trace_id (Story 016).

    This endpoint is only active when DEBUG_RAG is enabled; otherwise it
    returns 404 to avoid exposing internals unintentionally.
    """

    if not _DEBUG_SETTINGS.enabled:
        raise HTTPException(status_code=404, detail="Debugging disabled")

    # Optional token-based guard for the debug endpoint. When
    # DEBUG_ARTIFACTS_TOKEN is configured, require an Authorization header
    # with a matching bearer token. In production, the endpoint is disabled
    # entirely unless a token is set.
    expected_token = settings.DEBUG_ARTIFACTS_TOKEN
    if settings.ENVIRONMENT == "prod" and not expected_token:
        raise HTTPException(status_code=404, detail="Debugging disabled")

    if expected_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {expected_token}":
            raise HTTPException(status_code=403, detail="Forbidden")

    artifacts = await _ARTIFACT_STORAGE.get_by_trace_id(trace_id)
    return {"trace_id": trace_id, "artifacts": artifacts}


@router.post("/retrieve", response_model=RetrievalResponse, tags=["Retrieval"])
async def retrieve_endpoint(payload: RetrievalRequest) -> RetrievalResponse:
    """Return relevant chunks and metrics for a retrieval query.

    This endpoint exposes the retrieval layer directly: it runs the same
    embed → retrieve pipeline used by `/api/query` but returns a
    retrieval-centric view (chunks + similarity scores + metrics) without any
    generated answer text.
    """

    from backend.core.tracing import get_trace_context

    trace_ctx = get_trace_context()

    logger.info(
        "Retrieve endpoint called",
        extra={"query_preview": payload.query[:100], "top_k": payload.top_k},
    )

    internal_request = create_query_request(
        query_text=payload.query,
        top_k=payload.top_k,
        search_type="dense",
        filters=payload.filters or {},
        include_metadata=payload.include_sources,
        trace_context=trace_ctx,
    )

    try:
        internal_response = await _QUERY_ORCHESTRATOR.query(internal_request)
    except EmbeddingProviderError as exc:  # pragma: no cover - rare path
        logger.error(
            "Retrieval failed due to embedding provider error",
            exc_info=exc,
        )
        raise to_http_exception(ServiceUnavailableError()) from exc

    retrieved_chunks: List[RetrievalChunk] = []

    for rc in internal_response.retrieved_chunks:
        if rc.document_id is None:
            # Retrieval surface does not require document_id, but when it is not
            # present we also have very little useful source attribution, so we
            # skip such entries.
            continue

        if payload.include_sources:
            source: Dict[str, Any] = {"document_id": str(rc.document_id)}
            # Surface any known source-related metadata as-is.
            source.update(rc.metadata)
        else:
            source = {}

        retrieved_chunks.append(
            RetrievalChunk(
                chunk_id=rc.chunk_id,
                content=rc.content,
                similarity_score=rc.similarity_score,
                rank=rc.rank,
                source=source,
            )
        )

    metrics = RetrievalMetrics(
        embedding_latency_ms=float(
            internal_response.metrics.get("embedding_latency_ms", 0.0)
        ),
        retrieval_latency_ms=float(
            internal_response.metrics.get("retrieval_latency_ms", 0.0)
        ),
        total_latency_ms=float(internal_response.metrics.get("total_latency_ms", 0.0)),
        total_results_available=int(
            internal_response.metrics.get("total_results_available", 0)
        ),
        results_returned=len(retrieved_chunks),
    )

    return RetrievalResponse(
        query_id=internal_response.query_id,
        query_text=internal_response.query_text,
        retrieved_chunks=retrieved_chunks,
        metrics=metrics,
    )


@router.get("/metrics", tags=["Metrics"])
async def metrics() -> Dict[str, object]:
    """Prometheus-style metrics stub.

    Story 002 only requires that a metrics endpoint exists at the API gateway
    layer. A full Prometheus exposition format will be added in a later story.
    For now, we return a small JSON payload that is easy to extend.
    """

    return {
        "uptime_seconds": 0,
        "request_counters": {
            "health": 0,
            "ingest_upload": 0,
            "ingest_status": 0,
            "query": 0,
        },
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
    }


@router.get("/", tags=["Root"])
async def root() -> Dict[str, str]:
    """Root endpoint with basic API metadata."""

    return {
        "name": "RAG API",
        "version": settings.VERSION,
        "description": "Retrieval-Augmented Generation system",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
        "status": settings.ENVIRONMENT,
    }
