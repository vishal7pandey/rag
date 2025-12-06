"""Integration tests for OpenAI embedding client."""

from __future__ import annotations

import pytest

from backend.config.settings import settings
from backend.providers.openai_client import OpenAIEmbeddingClient

pytestmark = pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not configured",
)


@pytest.fixture
def embedding_client() -> OpenAIEmbeddingClient:
    """Initialize embedding client for testing."""

    return OpenAIEmbeddingClient(api_key=settings.OPENAI_API_KEY)


def test_embedding_client_connection(embedding_client: OpenAIEmbeddingClient) -> None:
    """Can connect to OpenAI embedding API."""

    assert embedding_client.client is not None


def test_embed_single_text(embedding_client: OpenAIEmbeddingClient) -> None:
    """Can embed a single text."""

    text = "This is a test document for embedding."

    result = embedding_client.embed(text)

    assert "embedding" in result
    assert len(result["embedding"]) == 1536
    assert result["model"] == "text-embedding-3-small"
    assert "usage" in result
    assert result["usage"]["total_tokens"] > 0


def test_embed_batch_texts(embedding_client: OpenAIEmbeddingClient) -> None:
    """Can embed multiple texts in a batch."""

    texts = [
        "First test document",
        "Second test document",
        "Third test document",
    ]

    results = embedding_client.embed_batch(texts)

    assert len(results) == 3
    for item in results:
        assert len(item["embedding"]) == 1536
        assert item["model"] == "text-embedding-3-small"


def test_embed_handles_empty_text(embedding_client: OpenAIEmbeddingClient) -> None:
    """Embedding client handles empty text gracefully."""

    with pytest.raises(ValueError, match="text cannot be empty"):
        embedding_client.embed("")


def test_embed_logs_latency(
    embedding_client: OpenAIEmbeddingClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Embedding client logs latency metrics."""

    text = "Test for latency logging"

    embedding_client.embed(text)

    assert any("latency_ms" in record.getMessage() for record in caplog.records)
