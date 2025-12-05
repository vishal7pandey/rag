"""Pydantic schemas for the backend API.

These models define the contracts between the React frontend and the FastAPI
backend for health, ingestion, and query endpoints.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# HEALTH ENDPOINT
# ============================================================================


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthResponse(BaseModel):
    """Response model for GET /health."""

    status: HealthStatus
    version: str = Field(..., description="API version (semver)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    environment: str = Field(
        default="dev", description="Deployment environment: dev, staging, or prod"
    )
    dependencies: Optional[Dict[str, str]] = Field(
        default=None,
        description="Status of external services such as vector_db and embedding_service.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "timestamp": "2025-12-04T23:44:00Z",
                "environment": "dev",
                "dependencies": {
                    "vector_db": "ok",
                    "embedding_service": "ok",
                },
            }
        }
    }


# ============================================================================
# INGESTION ENDPOINTS
# ============================================================================


class IngestionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentMetadata(BaseModel):
    """Metadata for uploaded documents."""

    category: str = Field(default="general")
    language: str = Field(default="en", description="ISO 639-1 code, e.g. 'en'")
    source: Optional[str] = Field(default=None)


class IngestionConfig(BaseModel):
    """Configuration for the ingestion pipeline."""

    chunk_size_tokens: int = Field(default=512, ge=100, le=4000)
    chunk_overlap_tokens: int = Field(default=50, ge=0, le=500)
    chunking_strategy: str = Field(default="semantic")
    embedding_model: str = Field(default="text-embedding-3-small")
    compute_sparse: bool = Field(default=True)
    enrich_metadata: bool = Field(default=True)


class IngestionResponse(BaseModel):
    """Response model for POST /api/ingest/upload and GET /api/ingest/status."""

    ingestion_id: UUID
    status: IngestionStatus
    document_id: Optional[UUID] = None
    chunks_created: int = Field(default=0, ge=0)
    progress_percent: int = Field(default=0, ge=0, le=100)
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("progress_percent")
    @classmethod
    def validate_progress(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("progress_percent must be between 0 and 100")
        return v


# ============================================================================
# QUERY ENDPOINT
# ============================================================================


class Chunk(BaseModel):
    """Core data unit flowing through the entire RAG system."""

    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    dense_embedding: List[float]
    sparse_embedding: Dict[str, float]
    metadata: Dict[str, Any]
    quality_score: Optional[float] = None
    embedding_model: str
    created_at: datetime
    updated_at: datetime


class QueryRequest(BaseModel):
    """Request body for POST /api/query."""

    query: str = Field(..., min_length=1, max_length=5000)
    top_k: int = Field(default=10, ge=1, le=100)
    filters: Optional[Dict[str, Any]] = None
    include_sources: bool = Field(default=True)


class QueryResponse(BaseModel):
    """Response body for POST /api/query."""

    query_id: UUID
    answer: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks: Optional[List[Chunk]] = None
    latency_ms: float = Field(ge=0)
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
