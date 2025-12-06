from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID, uuid4


if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from backend.core.query_models import RetrievedChunk  # type: ignore[name-defined]


@dataclass
class QueryRequest:
    """Internal query request model for similarity search.

    This is an execution-time representation and is distinct from the
    Pydantic API schema used by `/api/query`.
    """

    query_id: UUID
    query_text: str
    top_k: int = 10
    search_type: str = "dense"  # "dense" only in this story
    filters: Optional[Dict[str, Any]] = None
    include_metadata: bool = True
    trace_context: Optional[Dict[str, Any]] = None

    # Execution context populated during processing
    query_embedding: Optional[List[float]] = None
    retrieved_chunks: List["RetrievedChunk"] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RetrievedChunk:
    """A chunk returned from similarity search.

    This is an internal view built from stored embeddings and metadata.
    """

    chunk_id: UUID
    content: str
    similarity_score: float
    rank: int = 0
    retrieval_method: str = "dense"  # "dense" only in this story

    # Source attribution and metadata
    document_id: Optional[UUID] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    quality_score: Optional[float] = None

    # Vector and storage details (used when mapping to API schemas)
    embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class QueryResponseInternal:
    """Internal response model for similarity search orchestration.

    The public API still uses `backend.api.schemas.QueryResponse`. This
    model is used by the orchestration layer and then mapped onto the
    Pydantic schema at the API boundary.
    """

    query_id: UUID
    query_text: str
    retrieved_chunks: List[RetrievedChunk]
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_latency_ms(self) -> float:
        return float(self.metrics.get("total_latency_ms", 0.0))


def create_query_request(query_text: str, **kwargs: Any) -> QueryRequest:
    """Helper to construct a `QueryRequest` with a new UUID.

    This is primarily for tests and high-level orchestration code.
    """

    return QueryRequest(query_id=uuid4(), query_text=query_text, **kwargs)
