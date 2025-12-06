"""OpenAI provider clients for embeddings and generation.

Implements the OpenAIEmbeddingClient and OpenAIGenerationClient described in
Story 004, using the official `openai` SDK and the configuration classes from
`backend.config.openai_config`.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Iterator, List, Optional

from openai import OpenAI

from backend.config.openai_config import OpenAIEmbeddingConfig, OpenAIGenerationConfig

logger = logging.getLogger(__name__)


class OpenAIEmbeddingClient:
    """Client for OpenAI embeddings API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[OpenAIEmbeddingConfig] = None,
    ) -> None:
        """Initialize embedding client.

        Args:
            api_key: OpenAI API key (default: from env).
            config: Embedding configuration (default: from env).
        """

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

        self.config = config or OpenAIEmbeddingConfig.from_env()
        self.client = OpenAI(api_key=self.api_key)

        logger.info(
            "OpenAI embedding client initialized", extra={"model": self.config.model}
        )

    def embed(self, text: str) -> Dict[str, Any]:
        """Generate embedding for a single text.

        Returns a dict with keys: embedding, model, usage, latency_ms.
        """

        if not text or not text.strip():
            raise ValueError("text cannot be empty")

        start_time = time.time()

        try:
            response = self.client.embeddings.create(
                model=self.config.model,
                input=text,
            )

            latency_ms = (time.time() - start_time) * 1000

            result: Dict[str, Any] = {
                "embedding": response.data[0].embedding,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "latency_ms": latency_ms,
            }

            logger.warning(
                "Generated embedding latency_ms=%.2f" % latency_ms,
                extra={
                    "latency_ms": latency_ms,
                    "total_tokens": result["usage"]["total_tokens"],
                },
            )

            return result

        except Exception as exc:  # pragma: no cover - surfaced to caller
            logger.error("Embedding generation failed", exc_info=exc)
            raise

    def embed_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Generate embeddings for multiple texts in a batch."""

        if not texts:
            raise ValueError("texts list cannot be empty")

        all_results: List[Dict[str, Any]] = []
        batch_size = self.config.batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            start_time = time.time()

            try:
                response = self.client.embeddings.create(
                    model=self.config.model,
                    input=batch,
                )

                latency_ms = (time.time() - start_time) * 1000

                for data in response.data:
                    all_results.append(
                        {
                            "embedding": data.embedding,
                            "model": response.model,
                            "usage": {
                                "prompt_tokens": response.usage.prompt_tokens
                                // max(1, len(batch)),
                                "total_tokens": response.usage.total_tokens
                                // max(1, len(batch)),
                            },
                            "latency_ms": latency_ms / max(1, len(batch)),
                        }
                    )

                logger.warning(
                    "Generated batch embeddings latency_ms=%.2f" % latency_ms,
                    extra={
                        "batch_size": len(batch),
                        "latency_ms": latency_ms,
                        "total_tokens": response.usage.total_tokens,
                    },
                )

            except Exception as exc:  # pragma: no cover - surfaced to caller
                logger.error("Batch embedding failed", exc_info=exc)
                raise

        return all_results


class OpenAIGenerationClient:
    """Client for OpenAI chat completion (generation) API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[OpenAIGenerationConfig] = None,
    ) -> None:
        """Initialize generation client.

        Args:
            api_key: OpenAI API key (default: from env).
            config: Generation configuration (default: from env).
        """

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

        self.config = config or OpenAIGenerationConfig.from_env()
        self.client = OpenAI(api_key=self.api_key)

        logger.info(
            "OpenAI generation client initialized", extra={"model": self.config.model}
        )

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Generate a completion from chat messages.

        Returns content, model, usage, finish_reason, latency_ms.
        """

        if not messages:
            raise ValueError("messages cannot be empty")

        # The currently configured model (gpt-5-nano) does not allow overriding
        # temperature; only the default is supported. We still accept the
        # argument for API compatibility but do not forward it.
        max_tokens = (
            max_tokens
            if max_tokens is not None
            else self.config.default_max_output_tokens
        )

        start_time = time.time()

        try:
            # gpt-5-nano expects `max_completion_tokens` instead of `max_tokens`.
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_completion_tokens=max_tokens,
                stream=stream,
            )

            latency_ms = (time.time() - start_time) * 1000

            choice = response.choices[0]
            result: Dict[str, Any] = {
                "content": choice.message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "finish_reason": choice.finish_reason,
                "latency_ms": latency_ms,
            }

            logger.warning(
                "Generated completion latency_ms=%.2f" % latency_ms,
                extra={
                    "latency_ms": latency_ms,
                    "total_tokens": result["usage"]["total_tokens"],
                    "finish_reason": result["finish_reason"],
                },
            )

            return result

        except Exception as exc:  # pragma: no cover - surfaced to caller
            logger.error("Generation failed", exc_info=exc)
            raise

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """Generate a streamed completion from chat messages."""

        if not messages:
            raise ValueError("messages cannot be empty")

        # As above, we do not forward temperature for gpt-5-nano.
        max_tokens = (
            max_tokens
            if max_tokens is not None
            else self.config.default_max_output_tokens
        )

        try:
            # Use max_completion_tokens for newer chat models.
            stream = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_completion_tokens=max_tokens,
                stream=True,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

        except Exception as exc:  # pragma: no cover - surfaced to caller
            logger.error("Streaming generation failed", exc_info=exc)
            raise
