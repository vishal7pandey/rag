"""Integration tests for Pinecone upsert/query/delete operations.

These tests assume that Pinecone is configured (PINECONE_API_KEY set) and that
indexes have been provisioned (rag-dense / rag-sparse). If not, they are
skipped to avoid breaking CI.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from backend.data_layer.pinecone_client import PineconeClient


def _skip_reason() -> str | None:
    if not os.getenv("PINECONE_API_KEY"):
        return "PINECONE_API_KEY not set; Pinecone operation tests skipped"
    try:
        client = PineconeClient()
        client.list_indexes()
    except Exception as exc:  # pragma: no cover
        return f"Pinecone unavailable: {exc}"
    return None


@pytest.fixture(scope="module")
def pinecone_client() -> PineconeClient:
    reason = _skip_reason()
    if reason is not None:
        pytest.skip(reason)
    return PineconeClient()


def test_pinecone_upsert_and_query(pinecone_client: PineconeClient) -> None:
    """Can upsert a vector and then query it back."""

    test_id = f"test-chunk-{uuid4()}"
    vector = {
        "id": test_id,
        "values": [0.1] * 16,
        "metadata": {"source": "test.pdf", "page_number": 1},
    }

    upsert_result = pinecone_client.upsert_dense([vector])
    assert upsert_result is not None

    query_result = pinecone_client.query_dense(vector=[0.1] * 16, top_k=5)
    assert "matches" in query_result

    ids = {m["id"] for m in query_result.get("matches", [])}
    assert test_id in ids


def test_pinecone_delete(pinecone_client: PineconeClient) -> None:
    """Can delete vectors by id."""

    test_id = f"test-chunk-{uuid4()}"
    vector = {"id": test_id, "values": [0.2] * 16}
    pinecone_client.upsert_dense([vector])

    delete_result = pinecone_client.delete_dense([test_id])
    assert delete_result is not None
