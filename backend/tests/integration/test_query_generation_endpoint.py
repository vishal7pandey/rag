from __future__ import annotations

from uuid import uuid4


from backend.api import endpoints
from backend.api.schemas import QueryResponse
from backend.core.exceptions import RateLimitError
from backend.core.generation_models import (
    QueryGenerationMetadata,
    QueryGenerationRequest,
    QueryGenerationResponse,
)


class FailingGenerationOrchestrator:
    async def generate_answer(
        self,
        query_request: QueryGenerationRequest,
        trace_context: dict | None = None,
    ) -> QueryGenerationResponse:  # pragma: no cover - behavior tested via API
        raise RateLimitError("Too many requests", retry_after_seconds=10)


class StubGenerationOrchestrator:
    async def generate_answer(
        self,
        query_request: QueryGenerationRequest,
        trace_context: dict | None = None,
    ) -> QueryGenerationResponse:
        """Minimal happy-path stub that avoids real retrieval or LLM calls.

        This class deliberately does not subclass GenerationOrchestrator so that
        it does not attempt to construct a real OpenAIGenerationClient, which
        would require OPENAI_API_KEY.
        """

        meta = QueryGenerationMetadata(
            total_latency_ms=10.0,
            embedding_latency_ms=2.0,
            retrieval_latency_ms=3.0,
            prompt_assembly_latency_ms=1.0,
            generation_latency_ms=4.0,
            total_tokens_used=50,
            model="gpt-4o",
            chunks_retrieved=0,
        )

        return QueryGenerationResponse(
            query_id=uuid4(),
            answer="Stub answer",
            citations=[],
            used_chunks=[],
            metadata=meta,
        )


class FakeQueryOrchestrator:
    async def query(self, internal_request):  # type: ignore[override]
        """Return a minimal internal response shape used by the endpoint.

        This avoids calling the real QueryOrchestrator, which would depend on
        embedding configuration.
        """

        class _Resp:
            pass

        resp = _Resp()
        resp.query_id = uuid4()
        resp.query_text = internal_request.query_text
        resp.retrieved_chunks = []
        resp.total_latency_ms = 0.0
        return resp


def test_query_endpoint_uses_generation_metadata(monkeypatch, client) -> None:
    """When a generation orchestrator is configured, /api/query surfaces metadata."""

    monkeypatch.setattr(
        endpoints,
        "_GENERATION_ORCHESTRATOR",
        StubGenerationOrchestrator(),
        raising=False,
    )
    monkeypatch.setattr(
        endpoints,
        "_QUERY_ORCHESTRATOR",
        FakeQueryOrchestrator(),
        raising=False,
    )

    response = client.post("/api/query", json={"query": "What is policy?", "top_k": 5})

    assert response.status_code == 200

    data = response.json()
    model = QueryResponse(**data)

    assert model.metadata is not None
    assert model.metadata["total_latency_ms"] >= 0.0
    assert model.metadata["model"] == "gpt-4o"


def test_query_endpoint_llm_error_handling(monkeypatch, client) -> None:
    """LLM/provider errors are mapped to 503 with a friendly message."""

    monkeypatch.setattr(
        endpoints,
        "_GENERATION_ORCHESTRATOR",
        FailingGenerationOrchestrator(),
        raising=False,
    )

    response = client.post("/api/query", json={"query": "Test"})

    assert response.status_code == 503
    data = response.json()
    # The endpoint raises HTTPException with detail={"error": {...}}.
    assert "detail" in data
    assert "error" in data["detail"]
    message = str(data["detail"]["error"].get("message", "")).lower()
    assert "temporarily" in message or "unavailable" in message
