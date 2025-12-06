"""Pinecone client for vector storage and retrieval.

Implements the Story 003 contract using the Pinecone v3 client. This module
is responsible for basic connectivity and index access; higher-level storage
logic will live in a separate storage service.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pinecone import Pinecone

from backend.data_layer.config import PineconeConfig

logger = logging.getLogger(__name__)


class PineconeClient:
    """Client wrapper around the Pinecone Python SDK."""

    def __init__(self, config: Optional[PineconeConfig] = None) -> None:
        """Initialize Pinecone client from config or environment.

        If no config is provided, `PineconeConfig.from_env()` is used.
        """

        self.config = config or PineconeConfig.from_env()
        self._pc = Pinecone(api_key=self.config.api_key)
        logger.info(
            "Pinecone client initialized",
            extra={
                "environment": self.config.environment,
                "dense_index": self.config.dense_index_name,
                "sparse_index": self.config.sparse_index_name,
            },
        )

    # ------------------------------------------------------------------
    # Index helpers
    # ------------------------------------------------------------------

    def list_indexes(self) -> List[str]:
        """Return the list of index names available in the project."""

        return [idx.name for idx in self._pc.list_indexes()]

    def get_index(self, name: str) -> Any:
        """Return a raw Index handle by name."""

        return self._pc.Index(name)

    @property
    def dense_index(self) -> Any:
        """Return the configured dense index handle."""

        return self.get_index(self.config.dense_index_name)

    @property
    def sparse_index(self) -> Any:
        """Return the configured sparse index handle."""

        return self.get_index(self.config.sparse_index_name)

    # ------------------------------------------------------------------
    # Basic operations (dense vectors only for now)
    # ------------------------------------------------------------------

    def upsert_dense(self, vectors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert dense vectors into the dense index.

        Each vector dict should contain:
        - id: str
        - values: List[float]
        - metadata: Dict[str, Any] (optional)
        """

        result = self.dense_index.upsert(vectors=vectors)
        logger.info(
            "Upserted dense vectors",
            extra={"upserted_count": result.get("upserted_count")},
        )
        return result

    def query_dense(
        self,
        *,
        vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """Query the dense index for similar vectors."""

        results = self.dense_index.query(
            vector=vector,
            top_k=top_k,
            filter=filter,
            include_metadata=include_metadata,
        )
        logger.info(
            "Dense query executed",
            extra={"top_k": top_k, "matches": len(results.get("matches", []))},
        )
        return results

    def delete_dense(self, ids: List[str]) -> Dict[str, Any]:
        """Delete vectors by ID from the dense index."""

        result = self.dense_index.delete(ids=ids)
        logger.info("Deleted dense vectors", extra={"ids": ids})
        return result

    def describe_index_stats(self, index_name: Optional[str] = None) -> Dict[str, Any]:
        """Return index statistics for the given index or the dense index by default."""

        idx = self.get_index(index_name or self.config.dense_index_name)
        return idx.describe_index_stats()
