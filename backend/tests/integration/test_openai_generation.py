"""Integration tests for OpenAI generation client."""

from __future__ import annotations

import pytest

from backend.config.settings import settings
from backend.providers.openai_client import OpenAIGenerationClient

pytestmark = pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not configured",
)


@pytest.fixture
def generation_client() -> OpenAIGenerationClient:
    """Initialize generation client for testing."""

    return OpenAIGenerationClient(api_key=settings.OPENAI_API_KEY)


def test_generation_client_connection(
    generation_client: OpenAIGenerationClient,
) -> None:
    """Can connect to OpenAI generation API."""

    assert generation_client.client is not None


def test_generate_simple_response(generation_client: OpenAIGenerationClient) -> None:
    """Can generate a simple response."""

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is 2+2?"},
    ]

    result = generation_client.generate(messages)

    assert "content" in result and result["content"]
    # Allow date-suffixed variants such as gpt-5-nano-2025-08-07
    assert result["model"].startswith("gpt-5-nano")
    assert "usage" in result
    assert result["finish_reason"] in {"stop", "length"}


def test_generate_with_temperature(generation_client: OpenAIGenerationClient) -> None:
    """Can control temperature parameter."""

    messages = [{"role": "user", "content": "Say hello"}]

    result = generation_client.generate(messages, temperature=0.0)

    assert result["content"] is not None


def test_generate_handles_streaming(generation_client: OpenAIGenerationClient) -> None:
    """Generation client supports streaming."""

    messages = [{"role": "user", "content": "Count to 5"}]

    chunks = list(generation_client.generate_stream(messages))

    assert len(chunks) > 0
    full_response = "".join(chunks)
    assert len(full_response) > 0


def test_generate_logs_latency(
    generation_client: OpenAIGenerationClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Generation client logs latency metrics."""

    messages = [{"role": "user", "content": "Test"}]

    generation_client.generate(messages)

    assert any("latency_ms" in record.getMessage() for record in caplog.records)
