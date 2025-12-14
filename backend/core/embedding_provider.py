from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic.config import ConfigDict

from backend.core.embedding_models import (
    BatchEmbeddingConfig,
    Embedding,
    EmbeddingInput,
)

logger = logging.getLogger("rag.core.embedding_provider")


class EmbeddingProviderError(Exception):
    """Raised when the embedding provider exhausts retries or fails fatally."""


class _EmbeddingClientProtocol(BaseModel):  # type: ignore[misc]
    """Lightweight protocol-style wrapper used for type hints.

    We intentionally keep this minimal: any object with an ``embed_batch``
    method compatible with ``OpenAIEmbeddingClient.embed_batch`` can be used.
    This is primarily to make the provider easy to mock in tests.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: Any


class BatchEmbeddingProvider:
    """High-level batch embedding provider with retry and backoff.

    This class wraps a lower-level embedding client (e.g. ``OpenAIEmbeddingClient``)
    and adds:

    - batching based on ``BatchEmbeddingConfig.batch_size``
    - retry logic with exponential backoff
    - a simple, fully-mockable surface for unit tests

    All methods are async to integrate cleanly with async orchestration code,
    even though the underlying client is currently synchronous.
    """

    def __init__(
        self,
        config: BatchEmbeddingConfig,
        client: Optional[Any] = None,
    ) -> None:
        self.config = config
        self._client = client

    async def _call_api(self, texts: List[str]) -> List[List[float]]:
        """Call the underlying client for a batch of texts.

        This default implementation expects ``self._client`` to expose a
        ``embed_batch`` method compatible with ``OpenAIEmbeddingClient``.
        It runs the call in a thread pool via ``asyncio.to_thread`` so the
        outer API can remain async.
        """

        if self._client is None:
            raise EmbeddingProviderError(
                "No embedding client configured for BatchEmbeddingProvider"
            )

        # ``embed_batch`` is synchronous; run it in a thread to avoid blocking
        results: List[Dict[str, Any]] = await asyncio.to_thread(
            self._client.embed_batch,
            texts,
        )

        vectors: List[List[float]] = []
        for item in results:
            embedding = item.get("embedding")
            if not isinstance(
                embedding, list
            ):  # Defensive guard; should not happen in tests
                raise EmbeddingProviderError(
                    "Underlying client returned invalid embedding payload"
                )
            vectors.append(embedding)

        return vectors

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        """Determine whether an exception should trigger a retry.

        We treat HTTP 429 and 5xx-like errors as retryable when surfaced via a
        ``response.status_code`` attribute. For all other exceptions we default
        to retryable, except for obvious client-side errors like ``ValueError``.
        """

        if isinstance(exc, ValueError):
            return False

        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int) and status_code in {429, 500, 502, 503, 504}:
            return True

        # Default: assume retryable for transient network/SDK errors
        return True

    async def _embed_with_retries(
        self, texts: List[str], trace_context: Optional[Dict[str, Any]] = None
    ) -> List[List[float]]:
        attempts = 0
        delay = self.config.base_backoff_seconds

        while True:
            attempts += 1
            try:
                return await self._call_api(texts)
            except Exception as exc:  # pragma: no cover - branch exercised via tests
                if (
                    not self._is_retryable_error(exc)
                    or attempts > self.config.max_retries
                ):
                    logger.error(
                        "embedding_batch_failed",
                        extra={
                            "attempts": attempts,
                            "max_retries": self.config.max_retries,
                            "retryable": self._is_retryable_error(exc),
                            "error": str(exc),
                            "trace_context": trace_context or {},
                        },
                    )
                    raise EmbeddingProviderError(
                        f"Embedding provider failed after {attempts} attempts: {exc}"
                    ) from exc

                logger.warning(
                    "embedding_batch_retrying",
                    extra={
                        "attempt": attempts,
                        "max_retries": self.config.max_retries,
                        "delay_seconds": delay,
                        "error": str(exc),
                        "trace_context": trace_context or {},
                    },
                )
                await asyncio.sleep(delay)
                delay *= 2

    async def embed_batch(
        self,
        texts: List[str],
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> List[List[float]]:
        """Embed a list of texts, applying batching and retry logic.

        Returns a flat list of embedding vectors (one per input text).
        """

        if not texts:
            raise EmbeddingProviderError("texts list cannot be empty")

        batch_size = self.config.batch_size
        all_vectors: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            vectors = await self._embed_with_retries(batch, trace_context=trace_context)
            all_vectors.extend(vectors)

        return all_vectors

    async def embed_batch_with_metadata(
        self,
        inputs: List[EmbeddingInput],
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> List[Embedding]:
        """Embed a batch of ``EmbeddingInput`` objects and attach metadata.

        This is a convenience wrapper over ``embed_batch`` that returns
        fully-populated ``Embedding`` models aligned with the original
        inputs.
        """

        if not inputs:
            raise EmbeddingProviderError("inputs list cannot be empty")

        texts = [item.content for item in inputs]
        vectors = await self.embed_batch(texts, trace_context=trace_context)

        if len(vectors) != len(inputs):
            raise EmbeddingProviderError(
                "Provider returned a different number of embeddings than inputs"
            )

        embeddings: List[Embedding] = []
        for input_item, vector in zip(inputs, vectors):
            embeddings.append(
                Embedding(
                    chunk_id=input_item.chunk_id,
                    document_id=input_item.document_id,
                    content=input_item.content,
                    embedding=vector,
                    embedding_dimension=self.config.embedding_dimension,
                    metadata=input_item.metadata,
                    quality_score=input_item.quality_score,
                )
            )

        return embeddings
