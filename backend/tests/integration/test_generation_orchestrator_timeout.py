from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from backend.core.exceptions import QueryTimeoutError
from backend.core.generation_models import QueryGenerationRequest
from backend.core.generation_services import AnswerProcessor, GenerationOrchestrator
from backend.core.guardrails import TimeoutManager
from backend.core.prompt_services import PromptAssembler
from backend.core.query_models import QueryResponseInternal, RetrievedChunk


class FastQueryOrchestrator:
    async def query(self, request: Any) -> QueryResponseInternal:  # type: ignore[override]
        chunk = RetrievedChunk(
            chunk_id=uuid4(),
            content="Employees may work remotely up to 3 days per week.",
            similarity_score=0.92,
            rank=1,
            metadata={"source_file": "HRPolicy.pdf", "page": 3},
        )

        metrics: Dict[str, Any] = {
            "embedding_latency_ms": 10.0,
            "retrieval_latency_ms": 20.0,
            "total_latency_ms": 30.0,
            "total_results_available": 1,
        }

        return QueryResponseInternal(
            query_id=request.query_id,
            query_text=request.query_text,
            retrieved_chunks=[chunk],
            metrics=metrics,
        )


class SlowQueryOrchestrator:
    async def query(self, request: Any) -> QueryResponseInternal:  # type: ignore[override]
        # Simulate slow retrieval
        await asyncio.sleep(2.0)

        chunk = RetrievedChunk(
            chunk_id=uuid4(),
            content="Slow retrieval chunk.",
            similarity_score=0.5,
            rank=1,
            metadata={"source_file": "Slow.pdf", "page": 1},
        )

        metrics: Dict[str, Any] = {
            "embedding_latency_ms": 10.0,
            "retrieval_latency_ms": 1900.0,
            "total_latency_ms": 1910.0,
            "total_results_available": 1,
        }

        return QueryResponseInternal(
            query_id=request.query_id,
            query_text=request.query_text,
            retrieved_chunks=[chunk],
            metrics=metrics,
        )


class FastGenerationClient:
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Dict[str, Any]:  # type: ignore[override]
        return {
            "content": "Based on policy [Source 1], remote work is allowed.",
            "model": "gpt-5-nano",
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
            "finish_reason": "stop",
            "latency_ms": 42.0,
        }


class SlowGenerationClient:
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Dict[str, Any]:  # type: ignore[override]
        # Simulate a slow LLM call
        time.sleep(2.0)
        return {
            "content": "Slow answer [Source 1]",  # Shape compatible with AnswerProcessor
            "model": "gpt-5-nano",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "finish_reason": "stop",
            "latency_ms": 2000.0,
        }


@pytest.mark.asyncio
async def test_generation_orchestrator_completes_within_timeout() -> None:
    """Pipeline completes within timeout and returns latency metrics."""

    orchestrator = GenerationOrchestrator(
        query_orchestrator=FastQueryOrchestrator(),
        prompt_assembler=PromptAssembler(),
        generation_client=FastGenerationClient(),  # type: ignore[arg-type]
        answer_processor=AnswerProcessor(),
    )

    timeout_manager = TimeoutManager(timeout_seconds=30)
    request = QueryGenerationRequest(query="What is the remote work policy?", top_k=5)

    response = await orchestrator.generate_answer(
        request, timeout_manager=timeout_manager
    )

    meta = response.metadata
    assert meta.embedding_latency_ms >= 0
    assert meta.retrieval_latency_ms >= 0
    assert meta.prompt_assembly_latency_ms >= 0
    assert meta.generation_latency_ms >= 0
    assert meta.answer_processing_latency_ms >= 0
    assert meta.total_latency_ms > 0


@pytest.mark.asyncio
async def test_generation_orchestrator_timeout_during_retrieval() -> None:
    """Raises QueryTimeoutError if retrieval exceeds remaining time budget."""

    orchestrator = GenerationOrchestrator(
        query_orchestrator=SlowQueryOrchestrator(),
        prompt_assembler=PromptAssembler(),
        generation_client=FastGenerationClient(),  # type: ignore[arg-type]
        answer_processor=AnswerProcessor(),
    )

    timeout_manager = TimeoutManager(timeout_seconds=1)
    request = QueryGenerationRequest(query="test", top_k=5)

    with pytest.raises(QueryTimeoutError) as exc_info:
        await orchestrator.generate_answer(request, timeout_manager=timeout_manager)

    assert exc_info.value.status_code == 408
    assert exc_info.value.error_code == "timeout"


@pytest.mark.asyncio
async def test_generation_orchestrator_timeout_during_generation() -> None:
    """Raises QueryTimeoutError if generation exceeds remaining time budget."""

    orchestrator = GenerationOrchestrator(
        query_orchestrator=FastQueryOrchestrator(),
        prompt_assembler=PromptAssembler(),
        generation_client=SlowGenerationClient(),  # type: ignore[arg-type]
        answer_processor=AnswerProcessor(),
    )

    timeout_manager = TimeoutManager(timeout_seconds=1)
    request = QueryGenerationRequest(query="test", top_k=5)

    with pytest.raises(QueryTimeoutError) as exc_info:
        await orchestrator.generate_answer(request, timeout_manager=timeout_manager)

    assert exc_info.value.status_code == 408
    assert exc_info.value.error_code == "timeout"
