from __future__ import annotations

import time

from backend.core.query_cache import QueryEmbeddingCache


def test_cache_get_returns_none_for_unknown_query() -> None:
    cache = QueryEmbeddingCache()
    assert cache.get("unknown query") is None


def test_cache_set_and_get_round_trips_embedding() -> None:
    cache = QueryEmbeddingCache()
    embedding = [0.1, 0.2, 0.3]

    cache.set("test query", embedding)
    result = cache.get("test query")

    assert result == embedding
    # Ensure we got a copy, not the same list instance.
    assert result is not embedding


def test_cache_distinguishes_different_queries() -> None:
    cache = QueryEmbeddingCache()
    emb1 = [0.1, 0.2]
    emb2 = [0.3, 0.4]

    cache.set("query1", emb1)
    cache.set("query2", emb2)

    assert cache.get("query1") == emb1
    assert cache.get("query2") == emb2


def test_cache_expiration_respects_ttl() -> None:
    cache = QueryEmbeddingCache()
    embedding = [0.1, 0.2]

    cache.set("query", embedding, ttl_seconds=0.1)
    # Immediately available.
    assert cache.get("query") == embedding

    # After TTL has passed, entry should expire.
    time.sleep(0.2)
    assert cache.get("query") is None
