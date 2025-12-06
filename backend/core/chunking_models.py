"""Core chunking models for Story 008 (chunking pipeline).

These models represent the internal chunking contracts used by the core
pipeline. They are intentionally decoupled from API-facing schemas so that the
chunking implementation can evolve independently of storage/retrieval layers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """Single retrieval unit produced by the chunking pipeline.

    This is an internal core model and does not include embeddings; those are
    attached later in the storage/embedding layer.
    """

    chunk_id: UUID
    document_id: UUID
    content: str
    original_content: str

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Format-specific and domain metadata (page, section, etc.)",
    )

    # Quality metrics
    token_count: int
    word_count: int
    char_count: int
    quality_score: float

    # Downstream tracking flags
    has_valid_embedding: bool = False
    is_duplicate: bool = False

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChunkingConfig(BaseModel):
    """Configuration for chunking strategy.

    For Story 008, we operate purely in character space while approximating
    token counts at a higher level. Future stories may introduce real
    token-based configuration and mapping from ingestion settings.
    """

    strategy: str = Field(
        default="recursive",
        description="Chunking strategy: 'sliding_window' or 'recursive'",
    )

    # Sliding-window specific (character-based)
    chunk_size_chars: int = Field(
        default=2000,
        ge=100,
        le=8000,
        description="Target chunk size in characters (for sliding-window)",
    )
    chunk_overlap_chars: int = Field(
        default=200,
        ge=0,
        le=4000,
        description="Overlap between consecutive chunks in characters",
    )

    # Recursive specific
    separators: List[str] = Field(
        default_factory=lambda: ["\n\n", "\n", ".", " "],
        description="Separators for recursive splitting (tried in order)",
    )
    keep_separator: bool = Field(
        default=False,
        description="Keep separator attached to preceding chunk or discard",
    )

    # Both
    min_chunk_size_chars: int = Field(
        default=10,
        description="Minimum characters per chunk (smaller chunks discarded)",
    )
    max_chunk_size_chars: int = Field(
        default=8000,
        description="Maximum characters per chunk (larger chunks truncated)",
    )


class ChunkingResult(BaseModel):
    """Result of chunking operation for a single document."""

    document_id: UUID
    total_chunks: int
    chunks: List[Chunk]
    chunking_config: ChunkingConfig
    chunking_duration_ms: float

    quality_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregate metrics about chunking quality.",
    )
