"""API route handlers for the backend service.

This module defines the HTTP endpoints for health checks, ingestion, and query
operations. Business logic is stubbed for now and will be implemented in
later stories.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.api.errors import (
    BadRequestError,
    ServiceUnavailableError,
    to_http_exception,
)
from backend.api.schemas import (
    DocumentMetadata,
    HealthResponse,
    HealthStatus,
    IngestionConfig,
    IngestionResponse,
    IngestionStatus,
    QueryRequest,
    QueryResponse,
)
from backend.config.settings import settings
from backend.core.logging import get_logger


router = APIRouter()
logger = get_logger("rag.api.endpoints")


# In-memory store for ingestion status (stub implementation)
_INGESTION_STORE: Dict[UUID, IngestionResponse] = {}


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
        timestamp=datetime.utcnow(),
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
    """Accept document upload and return an ingestion_id (stubbed).

    In addition to files, this endpoint accepts optional JSON-encoded
    `document_metadata` and `ingestion_config` fields as described in
    Story 002. These are validated and logged but not yet persisted.
    """

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    metadata_model: Optional[DocumentMetadata] = None
    config_model: Optional[IngestionConfig] = None

    if document_metadata is not None:
        try:
            metadata_model = DocumentMetadata(**json.loads(document_metadata))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Invalid document_metadata payload", exc_info=exc)
            raise to_http_exception(
                BadRequestError(detail="Invalid document_metadata")
            ) from exc

    if ingestion_config is not None:
        try:
            config_model = IngestionConfig(**json.loads(ingestion_config))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Invalid ingestion_config payload", exc_info=exc)
            raise to_http_exception(
                BadRequestError(detail="Invalid ingestion_config")
            ) from exc

    ingestion_id = uuid4()

    # Note: real implementation will persist status and enqueue background work.
    resp = IngestionResponse(
        ingestion_id=ingestion_id,
        status=IngestionStatus.PENDING,
    )
    _INGESTION_STORE[ingestion_id] = resp

    logger.info(
        "Ingestion upload accepted",
        extra={
            "ingestion_id": str(ingestion_id),
            "file_count": len(files),
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


@router.post("/api/query", response_model=QueryResponse, tags=["Query"])
async def query_endpoint(payload: QueryRequest) -> QueryResponse:
    """Stub implementation of the query endpoint.

    For now, if there are no documents indexed, return a helpful message and
    an empty citations list, as per the Story 002 spec.
    """

    answer = (
        "I have no documents in my knowledge base yet. Please upload documents first."
    )

    logger.info(
        "Query endpoint called",
        extra={"query_preview": payload.query[:100], "top_k": payload.top_k},
    )

    return QueryResponse(
        query_id=uuid4(),
        answer=answer,
        citations=[],
        retrieved_chunks=[],
        latency_ms=50.0,
        confidence_score=None,
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
