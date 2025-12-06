from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.api.schemas import (
    DocumentMetadata,
    HealthResponse,
    IngestionConfig,
    IngestionResponse,
    QueryRequest,
)


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


def test_document_metadata_defaults_and_overrides() -> None:
    """DocumentMetadata provides sensible defaults and accepts overrides."""

    default_meta = DocumentMetadata()
    assert default_meta.category == "general"
    assert default_meta.language == "en"
    assert default_meta.source is None

    custom_meta = DocumentMetadata(
        category="technical", language="fr", source="unit-test"
    )
    assert custom_meta.category == "technical"
    assert custom_meta.language == "fr"
    assert custom_meta.source == "unit-test"


def test_ingestion_config_validation_ranges() -> None:
    """IngestionConfig enforces reasonable ranges for chunking parameters."""

    cfg = IngestionConfig(chunk_size_tokens=512, chunk_overlap_tokens=32)
    assert cfg.chunk_size_tokens == 512
    assert cfg.chunk_overlap_tokens == 32

    # Too-large chunk_size_tokens should fail validation
    with pytest.raises(ValidationError):
        IngestionConfig(chunk_size_tokens=5000)


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
