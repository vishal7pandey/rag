from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

import pytest

from backend.core.generation_models import QueryGenerationRequest
from backend.core.generation_services import AnswerProcessor, GenerationOrchestrator
from backend.core.prompt_services import PromptAssembler
from backend.core.query_models import QueryResponseInternal, RetrievedChunk


class FakeQueryOrchestrator:
    async def query(self, request: Any) -> QueryResponseInternal:
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


class FakeGenerationClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        self.calls.append({"messages": messages, "max_tokens": max_tokens})

        return {
            "content": "Based on policy [Source 1], remote work is allowed.",
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
            "finish_reason": "stop",
            "latency_ms": 42.0,
        }


@pytest.mark.asyncio
async def test_generation_orchestrator_full_pipeline() -> None:
    fake_query_orch = FakeQueryOrchestrator()
    prompt_assembler = PromptAssembler()
    fake_generation_client = FakeGenerationClient()
    answer_processor = AnswerProcessor()

    orchestrator = GenerationOrchestrator(
        query_orchestrator=fake_query_orch,
        prompt_assembler=prompt_assembler,
        generation_client=fake_generation_client,  # type: ignore[arg-type]
        answer_processor=answer_processor,
    )

    request = QueryGenerationRequest(query="What is the remote work policy?", top_k=5)

    response = await orchestrator.generate_answer(request)

    assert response.query_id is not None
    assert "remote work" in response.answer.lower()

    # At least one citation and used chunk should be produced.
    assert len(response.citations) >= 1
    assert response.citations[0].source_index == 1
    assert len(response.used_chunks) >= 1

    # Metadata should contain reasonable, non-negative latencies and token counts.
    meta = response.metadata
    assert meta.total_latency_ms >= 0.0
    assert meta.embedding_latency_ms >= 0.0
    assert meta.retrieval_latency_ms >= 0.0
    assert meta.prompt_assembly_latency_ms >= 0.0
    assert meta.generation_latency_ms >= 0.0
    assert meta.total_tokens_used == 70
    assert meta.chunks_retrieved == 1
