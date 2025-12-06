from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.core.embedding_models import Embedding


class VectorDBStorageLayer:
    """Abstract storage layer for embeddings.

    This provides the interface expected by the embedding service. In this
    story we implement an in-memory version suitable for unit tests and local
    experimentation; a PostgreSQL/pgvector-backed implementation will be
    introduced in a later story.
    """

    async def store_embedding(
        self, embedding: Embedding
    ) -> bool:  # pragma: no cover - interface only
        raise NotImplementedError

    async def store_embeddings_batch(
        self, embeddings: List[Embedding]
    ) -> Dict[str, Any]:  # pragma: no cover - interface only
        raise NotImplementedError

    async def search_by_similarity(
        self,
        embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Embedding]:  # pragma: no cover - interface only
        raise NotImplementedError

    async def search_by_document(
        self, document_id: UUID
    ) -> List[Embedding]:  # pragma: no cover - interface only
        raise NotImplementedError

    async def check_duplicate_content(
        self, content: str
    ) -> Optional[Embedding]:  # pragma: no cover - interface only
        raise NotImplementedError


class InMemoryVectorDBStorageLayer(VectorDBStorageLayer):
    """In-memory implementation of the vector storage layer.

    Embeddings are stored in a simple dictionary keyed by ``embedding_id``.
    Similarity search uses cosine similarity over the in-memory vectors. This
    implementation is designed for unit tests and local development only.
    """

    def __init__(self) -> None:
        self._store: Dict[UUID, Embedding] = {}

    async def store_embedding(self, embedding: Embedding) -> bool:
        self._store[embedding.embedding_id] = embedding
        return True

    async def store_embeddings_batch(
        self, embeddings: List[Embedding]
    ) -> Dict[str, Any]:
        failures: List[Dict[str, Any]] = []
        for emb in embeddings:
            await self.store_embedding(emb)
        return {
            "stored_count": len(embeddings),
            "failed_count": 0,
            "failures": failures,
        }

    async def search_by_similarity(
        self,
        embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Embedding]:
        """Return the top-k most similar embeddings by cosine similarity.

        If ``filters`` are provided, only embeddings whose metadata match all
        key/value pairs are considered.
        """

        if not self._store:
            return []

        def matches_filters(candidate: Embedding) -> bool:
            if not filters:
                return True
            for key, value in filters.items():
                if candidate.metadata.get(key) != value:
                    return False
            return True

        def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
            # Guard against dimension mismatch; such vectors are considered
            # non-comparable and given similarity 0.0.
            if len(vec_a) != len(vec_b) or not vec_a:
                return 0.0

            dot = 0.0
            norm_a = 0.0
            norm_b = 0.0
            for a, b in zip(vec_a, vec_b):
                dot += a * b
                norm_a += a * a
                norm_b += b * b

            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0

            return dot / (norm_a**0.5 * norm_b**0.5)

        scored: List[tuple[float, Embedding]] = []
        for emb in self._store.values():
            if not matches_filters(emb):
                continue
            score = cosine_similarity(embedding, emb.embedding)
            scored.append((score, emb))

        # Sort by similarity descending and take top_k
        scored.sort(key=lambda item: item[0], reverse=True)

        return [emb for score, emb in scored[:top_k] if score > 0.0]

    async def search_by_document(self, document_id: UUID) -> List[Embedding]:
        return [emb for emb in self._store.values() if emb.document_id == document_id]

    async def check_duplicate_content(self, content: str) -> Optional[Embedding]:
        for emb in self._store.values():
            if emb.content == content:
                return emb
        return None
