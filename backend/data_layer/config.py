"""Configuration objects for vector DB and metadata DB.

This module defines typed configuration models for Pinecone and PostgreSQL,
loaded from environment variables. It is introduced in Story 003 to separate
storage-layer configuration from general app settings.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional


@dataclass
class PineconeConfig:
    """Configuration for Pinecone vector database."""

    api_key: str
    environment: str = "us-east-1"
    dense_index_name: str = "rag-dense"
    sparse_index_name: str = "rag-sparse"
    dimension: int = 1536
    metric: str = "cosine"

    def __post_init__(self) -> None:
        """Basic validation of required fields."""

        if not self.api_key:
            raise ValueError("PINECONE_API_KEY is not set")

    @classmethod
    def from_env(cls) -> "PineconeConfig":
        """Load configuration from environment variables.

        Required:
        - PINECONE_API_KEY
        Optional:
        - PINECONE_ENVIRONMENT (default: us-east-1)
        - DENSE_INDEX_NAME (default: rag-dense)
        - SPARSE_INDEX_NAME (default: rag-sparse)
        - VECTOR_DIMENSION (default: 1536)
        - VECTOR_METRIC (default: cosine)
        """

        api_key = os.getenv("PINECONE_API_KEY", "")
        if not api_key:
            raise ValueError("PINECONE_API_KEY is not set")

        environment = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
        dense_index_name = os.getenv("DENSE_INDEX_NAME", "rag-dense")
        sparse_index_name = os.getenv("SPARSE_INDEX_NAME", "rag-sparse")

        dimension_str = os.getenv("VECTOR_DIMENSION")
        dimension = int(dimension_str) if dimension_str is not None else 1536

        metric = os.getenv("VECTOR_METRIC", "cosine")

        return cls(
            api_key=api_key,
            environment=environment,
            dense_index_name=dense_index_name,
            sparse_index_name=sparse_index_name,
            dimension=dimension,
            metric=metric,
        )


@dataclass
class PostgresConfig:
    """Configuration for PostgreSQL metadata store."""

    host: str
    port: int
    database: str
    user: str
    password: str

    pool_min_size: int = 5
    pool_max_size: int = 20
    max_overflow: int = 10
    pool_timeout: int = 30

    def __post_init__(self) -> None:
        if self.pool_max_size < self.pool_min_size:
            raise ValueError("pool_max_size must be >= pool_min_size")

    @property
    def connection_string(self) -> str:
        """SQLAlchemy-style PostgreSQL connection string."""

        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @classmethod
    def from_env(
        cls,
        *,
        default_database: Optional[str] = None,
        default_user: Optional[str] = None,
        default_password: Optional[str] = None,
    ) -> "PostgresConfig":
        """Load configuration from environment variables.

        Environment variables:
        - DB_HOST (default: localhost)
        - DB_PORT (default: 5432)
        - DB_NAME (default: ragdb or provided default_database)
        - DB_USER (default: postgres or provided default_user)
        - DB_PASSWORD (required unless default_password provided)
        """

        host = os.getenv("DB_HOST", "localhost")
        port_str = os.getenv("DB_PORT", "5432")
        port = int(port_str)

        database = os.getenv("DB_NAME", default_database or "ragdb")
        user = os.getenv("DB_USER", default_user or "postgres")

        password = os.getenv("DB_PASSWORD", default_password or "")
        if not password:
            raise ValueError("DB_PASSWORD is not set")

        return cls(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )
