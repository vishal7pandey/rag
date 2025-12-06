from __future__ import annotations

import asyncio
from typing import List
from uuid import uuid4

import pytest

from backend.core.embedding_models import BatchEmbeddingConfig, EmbeddingInput
from backend.core.embedding_provider import (
    BatchEmbeddingProvider,
    EmbeddingProviderError,
)


@pytest.mark.asyncio
async def test_provider_embeds_single_batch() -> None:
    """Single batch of texts embedded successfully."""

    config = BatchEmbeddingConfig(batch_size=10, embedding_dimension=3)
    provider = BatchEmbeddingProvider(config=config)

    async def fake_call_api(texts: List[str]) -> List[List[float]]:  # type: ignore[override]
        assert texts == ["Hello world", "Testing embeddings", "API call"]
        return [[0.1, 0.2, 0.3] for _ in texts]

    # Monkeypatch the internal API call to avoid real network usage
    provider._call_api = fake_call_api  # type: ignore[assignment]

    texts = ["Hello world", "Testing embeddings", "API call"]
    embeddings = await provider.embed_batch(texts)

    assert len(embeddings) == 3
    assert all(len(vec) == 3 for vec in embeddings)


@pytest.mark.asyncio
async def test_provider_retries_on_transient_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider retries on transient errors and eventually succeeds."""

    config = BatchEmbeddingConfig(
        batch_size=5, max_retries=3, base_backoff_seconds=0.01
    )
    provider = BatchEmbeddingProvider(config=config)

    calls: List[str] = []

    async def flaky_call(texts: List[str]) -> List[List[float]]:  # type: ignore[override]
        calls.append("call")
        if len(calls) < 3:
            raise Exception("Temporary error")
        return [[0.1] * 3 for _ in texts]

    provider._call_api = flaky_call  # type: ignore[assignment]

    texts = ["Hello"]
    embeddings = await provider.embed_batch(texts)

    assert len(embeddings) == 1
    assert len(calls) == 3  # original + 2 retries


@pytest.mark.asyncio
async def test_provider_respects_max_retries() -> None:
    """Provider fails after max retries are exceeded."""

    config = BatchEmbeddingConfig(
        batch_size=5, max_retries=2, base_backoff_seconds=0.01
    )
    provider = BatchEmbeddingProvider(config=config)

    async def always_fail(texts: List[str]) -> List[List[float]]:  # type: ignore[override]
        raise Exception("Persistent error")

    provider._call_api = always_fail  # type: ignore[assignment]

    with pytest.raises(EmbeddingProviderError) as exc_info:
        await provider.embed_batch(["Hello"])

    assert "failed after" in str(exc_info.value)


@pytest.mark.asyncio
async def test_provider_exponential_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retry backoff increases exponentially based on base_backoff_seconds."""

    config = BatchEmbeddingConfig(batch_size=5, max_retries=2, base_backoff_seconds=1.0)
    provider = BatchEmbeddingProvider(config=config)

    async def flaky_call(texts: List[str]) -> List[List[float]]:  # type: ignore[override]
        raise Exception("Error")

    provider._call_api = flaky_call  # type: ignore[assignment]

    backoff_times: List[float] = []

    # Capture the original sleep function before monkeypatching so that we
    # can avoid recursively calling the patched version.
    original_sleep = asyncio.sleep

    async def track_sleep(delay: float) -> None:
        backoff_times.append(delay)
        # Do not actually sleep (or recurse); use the original implementation
        # with a zero delay to keep tests fast.
        await original_sleep(0)

    monkeypatch.setattr("backend.core.embedding_provider.asyncio.sleep", track_sleep)

    with pytest.raises(EmbeddingProviderError):
        await provider.embed_batch(["Hello"])

    # With max_retries=3, we expect two sleep calls: 1s, 2s
    assert backoff_times == [1.0, 2.0]


@pytest.mark.asyncio
async def test_provider_batches_correctly() -> None:
    """Large input list is split into batches respecting batch_size."""

    config = BatchEmbeddingConfig(batch_size=5, embedding_dimension=2)
    provider = BatchEmbeddingProvider(config=config)

    calls: List[List[str]] = []

    async def fake_call_api(texts: List[str]) -> List[List[float]]:  # type: ignore[override]
        calls.append(list(texts))
        return [[0.0, 1.0] for _ in texts]

    provider._call_api = fake_call_api  # type: ignore[assignment]

    texts = [f"Text {i}" for i in range(12)]
    embeddings = await provider.embed_batch(texts)

    assert len(embeddings) == 12
    # 12 texts with batch_size=5 -> 3 batches: 5, 5, 2
    assert len(calls) == 3
    assert len(calls[0]) == 5
    assert len(calls[1]) == 5
    assert len(calls[2]) == 2


@pytest.mark.asyncio
async def test_embed_batch_with_metadata_returns_embeddings() -> None:
    """embed_batch_with_metadata wraps embed_batch and attaches metadata correctly."""

    config = BatchEmbeddingConfig(batch_size=10, embedding_dimension=3)
    provider = BatchEmbeddingProvider(config=config)

    async def fake_call_api(texts: List[str]) -> List[List[float]]:  # type: ignore[override]
        return [[0.1, 0.2, 0.3] for _ in texts]

    provider._call_api = fake_call_api  # type: ignore[assignment]

    inputs = [
        EmbeddingInput(
            chunk_id=uuid4(),
            document_id=uuid4(),
            content=f"Chunk {i}",
            metadata={"page_number": i},
            token_count=10,
            quality_score=0.9,
        )
        for i in range(3)
    ]

    embeddings = await provider.embed_batch_with_metadata(inputs)

    assert len(embeddings) == 3
    for inp, emb in zip(inputs, embeddings):
        assert emb.chunk_id == inp.chunk_id
        assert emb.document_id == inp.document_id
        assert emb.content == inp.content
        assert emb.metadata["page_number"] == inp.metadata["page_number"]
        assert len(emb.embedding) == 3
