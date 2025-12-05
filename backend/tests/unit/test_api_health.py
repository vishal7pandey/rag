from backend.api.schemas import HealthResponse


def test_health_endpoint_status_code(client) -> None:
    """GET /health returns 200."""

    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_response_structure(client) -> None:
    """GET /health returns the expected response shape and values."""

    response = client.get("/health")
    data = response.json()

    # Basic keys
    assert "status" in data
    assert "version" in data
    assert "timestamp" in data
    assert "environment" in data

    # Validate via schema
    model = HealthResponse(**data)
    assert model.status.value in {"healthy", "degraded", "unhealthy"}
    assert model.version == "0.1.0"
    assert model.environment in {"dev", "staging", "prod"}


def test_health_endpoint_response_time(client) -> None:
    """GET /health should be fast enough for a health probe."""

    import time

    start = time.time()
    response = client.get("/health")
    elapsed_ms = (time.time() - start) * 1000

    assert response.status_code == 200
    assert elapsed_ms < 200, f"Health check took {elapsed_ms:.2f}ms (target: <200ms)"


def test_health_check_optional_dependencies(client) -> None:
    """If dependencies are present, they should have valid status values."""

    response = client.get("/health")
    data = response.json()

    deps = data.get("dependencies")
    if deps is not None:
        assert isinstance(deps, dict)
        for status in deps.values():
            assert status in {"ok", "degraded", "unavailable"}
