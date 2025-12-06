from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware import LoggingMiddleware


def _build_app() -> TestClient:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.add_middleware(LoggingMiddleware)

    return TestClient(app)


def test_logging_middleware_generates_trace_id_header() -> None:
    client = _build_app()

    response = client.get("/health")

    assert response.status_code == 200
    assert "X-Trace-ID" in response.headers
    assert response.headers["X-Trace-ID"]


def test_logging_middleware_respects_incoming_trace_id() -> None:
    client = _build_app()

    response = client.get("/health", headers={"X-Trace-ID": "test-trace-123"})

    assert response.status_code == 200
    assert response.headers.get("X-Trace-ID") == "test-trace-123"
