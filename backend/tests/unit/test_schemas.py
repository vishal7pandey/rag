from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.api.schemas import HealthResponse, IngestionResponse, QueryRequest


def test_health_response_valid() -> None:
    """HealthResponse accepts valid data and sets defaults."""

    data = {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": datetime.utcnow(),
        "environment": "dev",
    }
    resp = HealthResponse(**data)

    assert resp.status == "healthy"
    assert resp.version == "0.1.0"
    assert resp.environment in {"dev", "staging", "prod"}


def test_health_response_invalid_status() -> None:
    """HealthResponse rejects invalid status values."""

    data = {"status": "unknown", "version": "0.1.0"}
    with pytest.raises(ValidationError):
        HealthResponse(**data)


def test_ingestion_response_defaults() -> None:
    """IngestionResponse applies sensible defaults for counts and progress."""

    ingestion_id = uuid4()
    resp = IngestionResponse(ingestion_id=ingestion_id, status="pending")

    assert resp.chunks_created == 0
    assert resp.progress_percent == 0
    assert resp.error_message is None
    assert resp.document_id is None


def test_query_request_validation() -> None:
    """QueryRequest enforces non-empty and reasonably sized queries."""

    # Empty query rejected
    with pytest.raises(ValidationError):
        QueryRequest(query="")

    # Too-long query rejected
    with pytest.raises(ValidationError):
        QueryRequest(query="x" * 5001)

    # Valid query
    req = QueryRequest(query="What is the company policy?")
    assert len(req.query) > 0
