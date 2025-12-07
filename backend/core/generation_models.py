from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass
class QueryGenerationRequest:
    """User request for answer generation (internal model)."""

    query: str
    top_k: int = 10
    filters: Optional[Dict[str, Any]] = None
    include_sources: bool = True


@dataclass
class CitationEntry:
    """Citation to a source chunk used in the answer."""

    source_index: int
    chunk_id: UUID
    document_id: Optional[UUID]
    source_file: Optional[str]
    page: Optional[int]
    similarity_score: float
    preview: str


@dataclass
class UsedChunk:
    """Chunk that was used in the prompt context for answer generation."""

    chunk_id: UUID
    rank: int
    similarity_score: float
    content_preview: str


@dataclass
class QueryGenerationMetadata:
    """Metadata and metrics for generation."""

    total_latency_ms: float
    embedding_latency_ms: float
    retrieval_latency_ms: float
    prompt_assembly_latency_ms: float
    generation_latency_ms: float
    total_tokens_used: int
    model: str
    chunks_retrieved: int


@dataclass
class QueryGenerationResponse:
    """Internal response model with generated answer and diagnostics."""

    query_id: UUID
    answer: str
    citations: List[CitationEntry]
    used_chunks: List[UsedChunk]
    metadata: QueryGenerationMetadata
