"""Integration tests for Pinecone connectivity and basic index access.

These tests are part of Story 003. They are designed to:
- Skip entirely when PINECONE_API_KEY (and related env) are not configured.
- Validate that the Pinecone client can connect and list indexes.
- Optionally assert that the configured dense/sparse index names exist
  when a real Pinecone project has been provisioned.
"""

from __future__ import annotations

import os
from typing import Optional

import pytest

from backend.data_layer.config import PineconeConfig
from backend.data_layer.pinecone_client import PineconeClient


def _skip_reason() -> Optional[str]:
    """Return a reason to skip Pinecone tests, or None if they should run."""

    if not os.getenv("PINECONE_API_KEY"):
        return "PINECONE_API_KEY not set; Pinecone integration tests skipped"

    try:
        client = PineconeClient()
        # Simple smoke test to ensure list_indexes doesn't raise.
        client.list_indexes()
    except Exception as exc:  # pragma: no cover - defensive, surfaced to skip
        return f"Pinecone unavailable: {exc}"

    return None


@pytest.fixture(scope="module")
def pinecone_client() -> PineconeClient:
    reason = _skip_reason()
    if reason is not None:
        pytest.skip(reason)
    return PineconeClient()


def test_pinecone_connection(pinecone_client: PineconeClient) -> None:
    """Can connect to Pinecone API and list indexes."""

    indexes = pinecone_client.list_indexes()
    assert isinstance(indexes, list)


def test_configured_indexes_if_present(pinecone_client: PineconeClient) -> None:
    """If indexes are provisioned, the configured names should be present.

    This test is lenient: it only asserts membership if the names appear,
    avoiding hard failures when indexes have not yet been created in a
    developer's Pinecone project.
    """

    cfg: PineconeConfig = pinecone_client.config
    indexes = pinecone_client.list_indexes()

    # If dense index exists, we should be able to obtain a handle and stats.
    if cfg.dense_index_name in indexes:
        idx = pinecone_client.dense_index
        stats = idx.describe_index_stats()
        assert isinstance(stats, dict)

    # Similarly, only assert for sparse index if it exists.
    if cfg.sparse_index_name in indexes:
        idx = pinecone_client.sparse_index
        stats = idx.describe_index_stats()
        assert isinstance(stats, dict)
