from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional


@dataclass
class _CacheEntry:
    embedding: List[float]
    expires_at: datetime


class QueryEmbeddingCache:
    """Simple in-memory cache for query embeddings with TTL support.

    This is intentionally minimal and in-process only. It is sufficient for
    reducing duplicate embedding calls for identical query strings in this
    story. Persistence and distributed caching are out of scope.
    """

    def __init__(self) -> None:
        self._store: Dict[str, _CacheEntry] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def get(self, query_text: str) -> Optional[List[float]]:
        """Return cached embedding for the given query, or None if missing/expired."""

        entry = self._store.get(query_text)
        if entry is None:
            return None

        if entry.expires_at <= self._now():
            # Expired; remove and treat as miss.
            self._store.pop(query_text, None)
            return None

        # Return a shallow copy to avoid accidental mutation of cache state.
        return list(entry.embedding)

    def set(
        self, query_text: str, embedding: List[float], ttl_seconds: int = 86400
    ) -> None:
        """Store an embedding for a query with a TTL (default 24 hours)."""

        expires_at = self._now() + timedelta(seconds=ttl_seconds)
        self._store[query_text] = _CacheEntry(
            embedding=list(embedding),
            expires_at=expires_at,
        )
