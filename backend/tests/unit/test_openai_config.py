"""Test OpenAI configuration loading and validation."""

from __future__ import annotations


import pytest

from backend.config.openai_config import (
    OpenAIConfig,
    OpenAIEmbeddingConfig,
    OpenAIGenerationConfig,
)


def test_embedding_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Embedding config loads from environment variables."""

    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("OPENAI_EMBEDDING_BATCH_SIZE", "50")

    config = OpenAIEmbeddingConfig.from_env()

    assert config.model == "text-embedding-3-small"
    assert config.dimensions == 1536
    assert config.batch_size == 50


def test_embedding_config_rejects_wrong_model() -> None:
    """Embedding config raises error if wrong model specified."""

    with pytest.raises(ValueError, match="must be 'text-embedding-3-small'"):
        OpenAIEmbeddingConfig(model="text-embedding-3-large")


def test_generation_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Generation config loads from environment variables."""

    monkeypatch.setenv("OPENAI_GENERATION_MODEL", "gpt-5-nano")
    monkeypatch.setenv("OPENAI_TEMPERATURE", "0.5")

    config = OpenAIGenerationConfig.from_env()

    assert config.model == "gpt-5-nano"
    assert config.default_temperature == 0.5


def test_generation_config_rejects_wrong_model() -> None:
    """Generation config raises error if wrong model specified."""

    with pytest.raises(ValueError, match="must be 'gpt-5-nano'"):
        OpenAIGenerationConfig(model="gpt-4.1-mini")


def test_openai_config_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenAI config raises error if API key missing."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(
        ValueError, match="OPENAI_API_KEY environment variable is required"
    ):
        OpenAIConfig.from_env()


def test_openai_config_validates_api_key_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI config validates API key format."""

    monkeypatch.setenv("OPENAI_API_KEY", "invalid-key")

    with pytest.raises(ValueError, match="Invalid OPENAI_API_KEY format"):
        OpenAIConfig.from_env()


def test_openai_config_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    """Complete OpenAI config loads successfully."""

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-12345")
    monkeypatch.setenv("OPENAI_ORG_ID", "org-test")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("OPENAI_GENERATION_MODEL", "gpt-5-nano")

    config = OpenAIConfig.from_env()

    assert config.api_key == "sk-test-key-12345"
    assert config.organization_id == "org-test"
    assert config.embedding.model == "text-embedding-3-small"
    assert config.generation.model == "gpt-5-nano"
