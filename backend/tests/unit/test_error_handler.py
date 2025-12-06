from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handler import register_exception_handlers
from backend.core.exceptions import BadRequestError


def _build_app_with_error_route() -> TestClient:
    """Create a minimal app wired with the global error handler.

    This mirrors the production configuration in backend.main, where
    `register_exception_handlers(app)` is used to install the handler.
    """

    app = FastAPI()

    @app.get("/error")
    def error_endpoint() -> None:
        raise BadRequestError("Invalid input")

    register_exception_handlers(app)

    return TestClient(app)


def test_global_exception_handler_returns_json_envelope() -> None:
    client = _build_app_with_error_route()

    response = client.get("/error")
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    assert data["error"]["type"] == "BadRequestError"
    assert data["error"]["message"] == "Invalid input"
    assert data["error"]["status_code"] == 400


def test_global_exception_handler_includes_trace_id() -> None:
    client = _build_app_with_error_route()

    response = client.get("/error")
    data = response.json()

    assert "trace_id" in data["error"]
    assert isinstance(data["error"]["trace_id"], str)
    assert response.headers.get("X-Trace-ID") == data["error"]["trace_id"]
