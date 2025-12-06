"""Test database configuration loading and validation for vector DB story."""

import pytest

from backend.data_layer.config import PineconeConfig, PostgresConfig


def test_pinecone_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pinecone config loads from environment variables."""

    monkeypatch.setenv("PINECONE_API_KEY", "test-key")
    monkeypatch.setenv("PINECONE_ENVIRONMENT", "us-east-1")

    config = PineconeConfig.from_env()

    assert config.api_key == "test-key"
    assert config.environment == "us-east-1"
    assert config.dense_index_name == "rag-dense"


def test_pinecone_config_missing_api_key() -> None:
    """Pinecone config raises error if API key missing."""

    with pytest.raises(ValueError, match="PINECONE_API_KEY"):
        PineconeConfig(api_key="")


def test_postgres_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """PostgreSQL config builds connection string correctly."""

    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "ragdb")
    monkeypatch.setenv("DB_USER", "postgres")
    monkeypatch.setenv("DB_PASSWORD", "testpass")

    config = PostgresConfig.from_env()

    expected = "postgresql://postgres:testpass@localhost:5432/ragdb"
    assert config.connection_string == expected


def test_postgres_config_validation() -> None:
    """PostgreSQL config validates pool sizes."""

    with pytest.raises(ValueError):
        PostgresConfig(
            host="localhost",
            port=5432,
            database="ragdb",
            user="postgres",
            password="testpass",
            pool_min_size=10,
            pool_max_size=5,  # Invalid: max < min
        )
