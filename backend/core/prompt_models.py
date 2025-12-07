from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from backend.core.query_models import RetrievedChunk


@dataclass
class PromptConstructionRequest:
    """Internal request model for constructing a prompt from retrieved chunks."""

    request_id: UUID
    query_text: str
    retrieved_chunks: List[RetrievedChunk]

    # Optional conversation context
    conversation_history: Optional[List[Dict[str, str]]] = None
    # Optional few-shot examples
    include_few_shot: bool = False
    few_shot_examples: Optional[List[Dict[str, str]]] = None

    # Model / generation configuration
    model: str = "gpt-4o"
    max_tokens_for_response: int = 1500
    include_sources: bool = True

    # Tracing and metadata
    trace_context: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PromptConstructionResponse:
    """Internal response model containing the assembled prompt and metrics."""

    request_id: UUID
    system_message: str
    user_message: str

    # Citation tracking: {index -> metadata about the cited chunk}
    citation_map: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    # Token accounting metrics
    token_metrics: Dict[str, int] = field(default_factory=dict)

    # Execution metadata
    chunks_included: int = 0
    chunks_truncated: int = 0
    assembly_latency_ms: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def create_prompt_request(
    query_text: str,
    retrieved_chunks: List[RetrievedChunk],
    **kwargs: Any,
) -> PromptConstructionRequest:
    """Helper to construct a PromptConstructionRequest with a fresh request_id."""

    return PromptConstructionRequest(
        request_id=uuid4(),
        query_text=query_text,
        retrieved_chunks=retrieved_chunks,
        **kwargs,
    )
