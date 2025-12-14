from __future__ import annotations

import asyncio
import time
from math import sqrt
from typing import Any, Dict, List, Optional

from backend.core.embedding_provider import EmbeddingProviderError
from backend.core.logging import get_logger
from backend.core.query_cache import QueryEmbeddingCache
from backend.core.query_models import (
    QueryRequest,
    QueryResponseInternal,
    RetrievedChunk,
)
from backend.core.vector_storage import VectorDBStorageLayer


class QueryEmbeddingService:
    """Generate embeddings for query strings.

    The embedding client is injected to keep this service easy to test.
    Any object exposing ``embed(text: str) -> Dict[str, Any]`` compatible with
    ``OpenAIEmbeddingClient.embed`` can be used.
    """

    def __init__(self, client: Any | None = None) -> None:
        self._client = client
        self._logger = get_logger("rag.core.query_embedding_service")

    async def embed_query(
        self,
        query_text: str,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> List[float]:
        if self._client is None:
            raise EmbeddingProviderError(
                "No embedding client configured for QueryEmbeddingService"
            )

        if not query_text or not query_text.strip():
            raise ValueError("query_text cannot be empty")

        trace_context = trace_context or {}

        start = time.time()
        result: Dict[str, Any] = await asyncio.to_thread(self._client.embed, query_text)
        latency_ms = (time.time() - start) * 1000.0

        embedding = result.get("embedding")
        if not isinstance(embedding, list):
            raise EmbeddingProviderError("Embedding client returned invalid embedding")

        self._logger.info(
            "query_embedding_completed",
            extra={
                "context": {
                    "latency_ms": latency_ms,
                    "embedding_dim": len(embedding),
                    "trace_context": trace_context,
                }
            },
        )

        return embedding


class RetrieverService:
    """Execute dense similarity search against the vector storage layer."""

    def __init__(self, storage: VectorDBStorageLayer) -> None:
        self._storage = storage
        self._logger = get_logger("rag.core.retriever_service")

    async def retrieve(
        self,
        query_embedding: List[float],
        query_text: str,
        top_k: int = 10,
        search_type: str = "dense",
        filters: Optional[Dict[str, Any]] = None,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """Retrieve top-k similar chunks using dense similarity search.

        Currently this uses the in-memory vector DB and cosine similarity only.
        """

        trace_context = trace_context or {}

        start = time.time()
        embeddings = await self._storage.search_by_similarity(
            embedding=query_embedding,
            top_k=top_k,
            filters=filters,
        )
        retrieval_latency_ms = (time.time() - start) * 1000.0

        self._logger.info(
            "retrieval_completed",
            extra={
                "context": {
                    "top_k": top_k,
                    "search_type": search_type,
                    "result_count": len(embeddings),
                    "latency_ms": retrieval_latency_ms,
                    "trace_context": trace_context,
                }
            },
        )

        # Map embeddings to RetrievedChunk models.
        results: List[RetrievedChunk] = []

        def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
            if not vec_a or not vec_b or len(vec_a) != len(vec_b):
                return 0.0
            dot = sum(a * b for a, b in zip(vec_a, vec_b))
            norm_a = sqrt(sum(a * a for a in vec_a))
            norm_b = sqrt(sum(b * b for b in vec_b))
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            return dot / (norm_a * norm_b)

        for index, emb in enumerate(embeddings, start=1):
            vec = getattr(emb, "embedding", None) or []
            similarity = cosine_similarity(query_embedding, vec)
            similarity = max(0.0, min(1.0, float(similarity)))

            metadata: Dict[str, Any] = dict(getattr(emb, "metadata", {}) or {})

            chunk = RetrievedChunk(
                chunk_id=emb.chunk_id,
                content=emb.content,
                similarity_score=similarity,
                rank=index,
                retrieval_method=search_type,
                document_id=getattr(emb, "document_id", None),
                metadata=metadata,
                quality_score=getattr(emb, "quality_score", None),
                embedding=vec,
                embedding_model=getattr(emb, "embedding_model", None),
                created_at=getattr(emb, "created_at", None),
                updated_at=getattr(emb, "updated_at", None),
            )
            results.append(chunk)

        # We do not expose latency directly here; the orchestrator aggregates it.
        # Returning results is sufficient for this story.
        return results


class QueryOrchestrator:
    """Orchestrate query embedding generation and similarity retrieval."""

    def __init__(
        self,
        embedding_service: QueryEmbeddingService,
        retriever_service: RetrieverService,
        embedding_cache: Optional[QueryEmbeddingCache] = None,
    ) -> None:
        self._embedding_service = embedding_service
        self._retriever_service = retriever_service
        self._embedding_cache = embedding_cache
        self._logger = get_logger("rag.core.query_orchestrator")

    async def query(self, request: QueryRequest) -> QueryResponseInternal:
        """Execute embed → retrieve pipeline for a single query."""

        trace_context = request.trace_context or {}
        start_total = time.time()

        # Stage 1: Embed query text (with optional cache).
        start_embed = time.time()
        cache_hit = False
        query_embedding: List[float]

        if self._embedding_cache is not None:
            cached = self._embedding_cache.get(request.query_text)
            if cached is not None:
                query_embedding = cached
                cache_hit = True
            else:
                query_embedding = await self._embedding_service.embed_query(
                    request.query_text,
                    trace_context=trace_context,
                )
                self._embedding_cache.set(request.query_text, query_embedding)
        else:
            query_embedding = await self._embedding_service.embed_query(
                request.query_text,
                trace_context=trace_context,
            )

        embed_latency_ms = (time.time() - start_embed) * 1000.0
        request.query_embedding = query_embedding

        # Stage 2: Retrieve similar chunks
        start_retrieve = time.time()
        retrieved_chunks = await self._retriever_service.retrieve(
            query_embedding=query_embedding,
            query_text=request.query_text,
            top_k=request.top_k,
            search_type=request.search_type,
            filters=request.filters,
            trace_context=trace_context,
        )
        retrieval_latency_ms = (time.time() - start_retrieve) * 1000.0

        request.retrieved_chunks = retrieved_chunks

        total_latency_ms = (time.time() - start_total) * 1000.0

        self._logger.info(
            "query_completed",
            extra={
                "context": {
                    "query_id": str(request.query_id),
                    "top_k": request.top_k,
                    "result_count": len(retrieved_chunks),
                    "latency_ms": total_latency_ms,
                    "trace_context": trace_context,
                }
            },
        )

        metrics: Dict[str, Any] = {
            "embedding_latency_ms": embed_latency_ms,
            "retrieval_latency_ms": retrieval_latency_ms,
            "total_latency_ms": total_latency_ms,
            "search_type": request.search_type,
            "total_results_available": len(retrieved_chunks),
            "filters_applied": request.filters or {},
            "embedding_cache_enabled": self._embedding_cache is not None,
            "embedding_cache_hit": cache_hit,
        }

        return QueryResponseInternal(
            query_id=request.query_id,
            query_text=request.query_text,
            retrieved_chunks=retrieved_chunks,
            metrics=metrics,
        )
