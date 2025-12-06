from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class EmbeddingInput(BaseModel):
    """Input payload for the embedding layer, derived from a Chunk.

    This is an internal contract used by the embedding service and
    provider, not an API schema.
    """

    chunk_id: UUID
    document_id: UUID
    content: str
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Chunk metadata (page_number, section_title, etc.)",
    )
    token_count: int = Field(
        default=0,
        ge=0,
        description="Approximate token count for budgeting/metrics.",
    )
    quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Chunk quality score propagated from chunking.",
    )


class Embedding(BaseModel):
    """Persisted or in-memory vector embedding for a chunk."""

    embedding_id: UUID = Field(default_factory=uuid4)
    chunk_id: UUID
    document_id: UUID
    content: str

    # Vector data
    embedding: List[float] = Field(
        description="Dense vector representation (e.g. 1536-dim from OpenAI).",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model identifier.",
    )
    embedding_dimension: int = Field(
        default=1536,
        description="Expected embedding dimensionality.",
    )

    # Metadata and quality
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Chunk metadata (page_number, section_title, etc.)",
    )
    quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Chunk-level quality score (0.0–1.0).",
    )
    embedding_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Quality score derived from embedding properties.",
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BatchEmbeddingConfig(BaseModel):
    """Configuration for batch embedding operations."""

    batch_size: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of chunks per provider API call.",
    )
    model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model name used by the provider.",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts on provider failure.",
    )
    base_backoff_seconds: float = Field(
        default=1.0,
        description="Initial backoff in seconds for exponential backoff.",
    )
    timeout_seconds: float = Field(
        default=30.0,
        description="Timeout per provider API call in seconds.",
    )
    embedding_dimension: int = Field(
        default=1536,
        description="Expected embedding dimension.",
    )
    skip_duplicate_content: bool = Field(
        default=True,
        description="Skip embedding if identical content is already stored.",
    )


class EmbeddingFailure(BaseModel):
    """Represents a failed embedding attempt for a single chunk."""

    chunk_id: UUID
    error: str
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retries attempted for this chunk.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional extra context for the failure (e.g. status code).",
    )


class EmbeddingResult(BaseModel):
    """Result of an embedding + (optional) persistence operation."""

    total_inputs: int
    total_batches: int
    successful_embeddings: int
    failed_embeddings: int
    total_api_calls: int
    total_retries: int

    embeddings: List[Embedding] = Field(
        default_factory=list,
        description="Successfully generated (and possibly stored) embeddings.",
    )
    failures: List[EmbeddingFailure] = Field(
        default_factory=list,
        description="Details for failed embedding attempts.",
    )

    embedding_duration_ms: float = 0.0
    storage_duration_ms: float = 0.0
    total_duration_ms: float = 0.0

    quality_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregated quality and coverage metrics.",
    )
