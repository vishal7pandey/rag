from __future__ import annotations

from uuid import uuid4


from backend.api import endpoints
from backend.api.schemas import QueryResponse
from backend.config.debug_settings import DebugSettings
from backend.core.artifact_logger import ArtifactLogger
from backend.core.artifact_storage import InMemoryArtifactStorage
from backend.core.generation_models import (
    QueryGenerationMetadata,
    QueryGenerationRequest,
    QueryGenerationResponse,
)


class StubDebugGenerationOrchestrator:
    async def generate_answer(  # type: ignore[override]
        self,
        query_request: QueryGenerationRequest,
        trace_context: dict | None = None,
        timeout_manager: object | None = None,
        artifact_logger: ArtifactLogger | None = None,
    ) -> QueryGenerationResponse:
        """Stub orchestrator that logs all artifact types when debug is enabled."""

        if artifact_logger is not None:
            # Log fake artifacts for all stages so the debug endpoint has data.
            artifact_logger.log_retrieved_chunks_artifact(
                chunks=[], retrieval_latency_ms=10.0, trace_context=trace_context
            )
            artifact_logger.log_prompt_artifact(
                system_message="sys",
                user_message="user",
                token_breakdown={
                    "system_tokens": 1,
                    "context_tokens": 2,
                    "response_tokens": 3,
                },
                citation_map={},
                trace_context=trace_context,
            )
            artifact_logger.log_answer_artifact(
                answer_text="answer",
                raw_llm_output="raw",
                generation_latency_ms=5.0,
                model="gpt-5-nano",
                token_usage={"answer_tokens": 1, "prompt_tokens": 2, "total_tokens": 3},
                trace_context=trace_context,
            )
            metadata = QueryGenerationMetadata(
                total_latency_ms=10.0,
                embedding_latency_ms=1.0,
                retrieval_latency_ms=2.0,
                prompt_assembly_latency_ms=1.0,
                generation_latency_ms=3.0,
                answer_processing_latency_ms=1.0,
                total_tokens_used=10,
                model="gpt-5-nano",
                chunks_retrieved=0,
            )
            artifact_logger.log_response_artifact(
                answer="answer",
                citations=[],
                used_chunks=[],
                metadata=metadata,
                trace_context=trace_context,
            )

        meta = QueryGenerationMetadata(
            total_latency_ms=10.0,
            embedding_latency_ms=2.0,
            retrieval_latency_ms=3.0,
            prompt_assembly_latency_ms=1.0,
            generation_latency_ms=4.0,
            answer_processing_latency_ms=0.0,
            total_tokens_used=50,
            model="gpt-5-nano",
            chunks_retrieved=0,
        )

        return QueryGenerationResponse(
            query_id=uuid4(),
            answer="Stub answer",
            citations=[],
            used_chunks=[],
            metadata=meta,
        )


def test_debug_artifacts_endpoint_returns_artifacts(monkeypatch, client) -> None:
    """GET /api/debug/artifacts?trace_id=... returns artifacts when debug is enabled."""

    # Enable debug logging and use a fresh in-memory storage/logger.
    debug_settings = DebugSettings(enabled=True)
    storage = InMemoryArtifactStorage()
    logger = ArtifactLogger(debug_settings, storage)

    monkeypatch.setattr(endpoints, "_DEBUG_SETTINGS", debug_settings, raising=False)
    monkeypatch.setattr(endpoints, "_ARTIFACT_STORAGE", storage, raising=False)
    monkeypatch.setattr(endpoints, "_ARTIFACT_LOGGER", logger, raising=False)
    # Ensure the debug artifacts endpoint is accessible without an auth token for
    # this test, regardless of the environment's DEBUG_ARTIFACTS_TOKEN value.
    monkeypatch.setattr(endpoints.settings, "DEBUG_ARTIFACTS_TOKEN", "", raising=False)

    # Use a stub generation orchestrator that logs artifacts.
    monkeypatch.setattr(
        endpoints,
        "_GENERATION_ORCHESTRATOR",
        StubDebugGenerationOrchestrator(),
        raising=False,
    )

    trace_id = "test-trace-123"

    # Trigger a query with a known trace ID.
    response = client.post(
        "/api/query",
        json={"query": "test", "top_k": 5},
        headers={"X-Trace-ID": trace_id},
    )
    assert response.status_code == 200
    _ = QueryResponse(**response.json())

    # Fetch artifacts for that trace.
    artifacts_response = client.get(f"/api/debug/artifacts?trace_id={trace_id}")

    assert artifacts_response.status_code == 200
    data = artifacts_response.json()
    assert data["trace_id"] == trace_id
    artifact_types = [a["type"] for a in data["artifacts"]]
    # We expect at least the stubbed artifact types; query artifact may also be present.
    assert "retrieved_chunks" in artifact_types
    assert "prompt" in artifact_types
    assert "answer" in artifact_types
    assert "response" in artifact_types


def test_debug_artifacts_endpoint_disabled(monkeypatch, client) -> None:
    """When debug is disabled, the debug artifacts endpoint returns 404."""

    debug_settings = DebugSettings(enabled=False)
    monkeypatch.setattr(endpoints, "_DEBUG_SETTINGS", debug_settings, raising=False)

    response = client.get("/api/debug/artifacts?trace_id=test")
    assert response.status_code == 404
