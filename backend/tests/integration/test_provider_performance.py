"""Performance tests for OpenAI provider latency and batching.

These tests are intentionally light and are skipped when OPENAI_API_KEY is not
configured to avoid breaking CI in environments without credentials.
"""

from __future__ import annotations

import time

import pytest

from backend.config.settings import settings
from backend.providers.openai_client import (
    OpenAIEmbeddingClient,
    OpenAIGenerationClient,
)

pytestmark = pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not configured",
)


def test_embedding_latency_under_threshold() -> None:
    """Embedding latency is under a reasonable threshold for typical input."""

    client = OpenAIEmbeddingClient(api_key=settings.OPENAI_API_KEY)
    text = "This is a typical document chunk for embedding."

    start = time.time()
    client.embed(text)
    latency_ms = (time.time() - start) * 1000

    # Use a relatively generous threshold to avoid flakes while still catching
    # severe regressions in typical environments.
    assert latency_ms < 5000, f"Embedding took {latency_ms:.2f}ms"


def test_generation_latency_under_threshold() -> None:
    """Generation latency is under a reasonable threshold for a simple query."""

    client = OpenAIGenerationClient(api_key=settings.OPENAI_API_KEY)
    messages = [{"role": "user", "content": "What is AI?"}]

    start = time.time()
    client.generate(messages, max_tokens=100)
    latency_ms = (time.time() - start) * 1000

    assert latency_ms < 5000, f"Generation took {latency_ms:.2f}ms"


def test_batch_embedding_efficiency() -> None:
    """Batch embedding should be at least as efficient as multiple single calls."""

    client = OpenAIEmbeddingClient(api_key=settings.OPENAI_API_KEY)
    texts = [f"Test document {i}" for i in range(10)]

    # Batch call
    start_batch = time.time()
    client.embed_batch(texts)
    batch_time = time.time() - start_batch

    # Individual calls (sample 3 for comparison, extrapolated to 10)
    start_individual = time.time()
    for text in texts[:3]:
        client.embed(text)
    individual_time = (time.time() - start_individual) * (10 / 3)

    assert batch_time <= individual_time, (
        "Batch embedding was slower than individual calls"
    )
