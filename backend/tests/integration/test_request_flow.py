import asyncio
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware import LoggingMiddleware
from backend.api.schemas import QueryRequest, QueryResponse
from backend.core.logging import get_logger


def _build_app() -> TestClient:
    app = FastAPI()

    @app.post("/api/query", response_model=QueryResponse)
    async def query_endpoint(request: QueryRequest) -> QueryResponse:  # type: ignore[unused-ignore]
        logger = get_logger("rag.query")
        logger.info(
            "query_received",
            extra={"context": {"query_preview": request.query[:50]}},
        )

        await asyncio.sleep(0.01)

        logger.info("query_processed")

        return QueryResponse(
            query_id=uuid4(),
            answer="Test answer",
            citations=[],
            retrieved_chunks=[],
            latency_ms=10.0,
            confidence_score=None,
        )

    app.add_middleware(LoggingMiddleware)

    return TestClient(app)


def test_full_request_flow_with_tracing() -> None:
    """End-to-end request flow verifies trace ID propagation and success."""

    client = _build_app()

    response = client.post(
        "/api/query",
        json={"query": "What is AI?"},
        headers={"X-Trace-ID": "test-trace-123"},
    )

    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == "test-trace-123"
