"""OpenAI provider configuration for embeddings and generation.

Implements the configuration classes described in Story 004:
- OpenAIEmbeddingConfig
- OpenAIGenerationConfig
- OpenAIConfig

These are simple dataclasses that load from environment variables and enforce
standardized model names and basic validation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OpenAIEmbeddingConfig:
    """Configuration for OpenAI embeddings."""

    model: str = "text-embedding-3-small"  # STANDARDIZED
    dimensions: int = 1536
    max_input_tokens: int = 8191
    batch_size: int = 100
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0

    @classmethod
    def from_env(cls) -> "OpenAIEmbeddingConfig":
        """Load embedding configuration from environment variables."""

        return cls(
            model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            batch_size=int(os.getenv("OPENAI_EMBEDDING_BATCH_SIZE", "100")),
        )

    def __post_init__(self) -> None:
        """Validate configuration values."""

        if self.model != "text-embedding-3-small":
            raise ValueError(
                "Model must be 'text-embedding-3-small', got "
                f"'{self.model}'. This is standardized across the system."
            )
        if self.dimensions != 1536:
            raise ValueError(f"Dimensions must be 1536 for {self.model}")
        if not 1 <= self.batch_size <= 2048:
            raise ValueError("Batch size must be between 1 and 2048")


@dataclass
class OpenAIGenerationConfig:
    """Configuration for OpenAI text generation."""

    model: str = "gpt-5-nano"  # STANDARDIZED
    max_tokens: int = 128000  # Context window
    default_temperature: float = 0.3
    default_max_output_tokens: int = 1000
    timeout_seconds: int = 60
    retry_attempts: int = 3
    retry_delay_seconds: float = 2.0
    stream_enabled: bool = True

    @classmethod
    def from_env(cls) -> "OpenAIGenerationConfig":
        """Load generation configuration from environment variables."""

        return cls(
            model=os.getenv("OPENAI_GENERATION_MODEL", "gpt-5-nano"),
            default_temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.3")),
        )

    def __post_init__(self) -> None:
        """Validate configuration values."""

        if self.model != "gpt-5-nano":
            raise ValueError(
                "Model must be 'gpt-5-nano', got "
                f"'{self.model}'. This is standardized across the system."
            )
        if not 0.0 <= self.default_temperature <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        if not 1 <= self.default_max_output_tokens <= self.max_tokens:
            raise ValueError("Max output tokens must be between 1 and max_tokens")


@dataclass
class OpenAIConfig:
    """Complete OpenAI provider configuration."""

    api_key: str
    organization_id: Optional[str] = None
    embedding: OpenAIEmbeddingConfig = field(default_factory=OpenAIEmbeddingConfig)
    generation: OpenAIGenerationConfig = field(default_factory=OpenAIGenerationConfig)

    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        """Load complete configuration from environment variables."""

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        return cls(
            api_key=api_key,
            organization_id=os.getenv("OPENAI_ORG_ID"),
            embedding=OpenAIEmbeddingConfig.from_env(),
            generation=OpenAIGenerationConfig.from_env(),
        )

    def __post_init__(self) -> None:
        """Validate top-level configuration values."""

        if not self.api_key or not self.api_key.startswith("sk-"):
            raise ValueError("Invalid OPENAI_API_KEY format")
