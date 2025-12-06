"""Unified storage service for chunks across Pinecone + PostgreSQL.

This is a thin integration layer introduced in Story 003. It is intentionally
simple and focused on basic operations that are easy to test:

- store_chunk: write a Chunk into Pinecone (dense) and Postgres.
- get_chunk_by_id: read a Chunk back from Postgres by id.
- batch_store_chunks: store multiple chunks and return simple counters.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable
from uuid import UUID

from sqlalchemy import text

from backend.api.schemas import Chunk
from backend.data_layer.pinecone_client import PineconeClient
from backend.data_layer.postgres_client import PostgresClient

logger = logging.getLogger(__name__)


class StorageService:
    """Service coordinating storage between Pinecone and Postgres."""

    def __init__(
        self,
        *,
        pinecone_client: PineconeClient | None = None,
        postgres_client: PostgresClient | None = None,
    ) -> None:
        self.pinecone = pinecone_client or PineconeClient()
        self.postgres = postgres_client or PostgresClient()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store_chunk(self, chunk: Chunk) -> Dict[str, bool]:
        """Store a single chunk in both Pinecone and Postgres.

        Returns a dict with keys `pinecone_success` and `postgres_success`.
        """

        pinecone_success = False
        postgres_success = False

        # Store dense embedding and metadata in Pinecone
        try:
            vector = {
                "id": str(chunk.id),
                "values": chunk.dense_embedding,
                "metadata": {
                    **(chunk.metadata or {}),
                    "document_id": str(chunk.document_id),
                    "chunk_index": chunk.chunk_index,
                },
            }
            self.pinecone.upsert_dense([vector])
            pinecone_success = True
        except Exception as exc:  # pragma: no cover - surfaced via return
            logger.error("Failed to upsert chunk into Pinecone", exc_info=exc)

        # Store content and metadata in Postgres
        try:
            with self.postgres.engine.begin() as conn:
                # Ensure document row exists (minimal fields)
                conn.execute(
                    text(
                        """
                        INSERT INTO documents (id, filename)
                        VALUES (:doc_id, :filename)
                        ON CONFLICT (id) DO NOTHING
                        """
                    ),
                    {
                        "doc_id": str(chunk.document_id),
                        "filename": chunk.metadata.get("source", "unknown")
                        if chunk.metadata
                        else "unknown",
                    },
                )

                conn.execute(
                    text(
                        """
                        INSERT INTO chunks (
                            id,
                            document_id,
                            chunk_index,
                            content,
                            embedding_model,
                            source,
                            language,
                            page_number,
                            user_id,
                            quality_score
                        )
                        VALUES (
                            :id,
                            :document_id,
                            :chunk_index,
                            :content,
                            :embedding_model,
                            :source,
                            :language,
                            :page_number,
                            :user_id,
                            :quality_score
                        )
                        ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                            content = EXCLUDED.content,
                            quality_score = EXCLUDED.quality_score
                        """
                    ),
                    {
                        "id": str(chunk.id),
                        "document_id": str(chunk.document_id),
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "embedding_model": chunk.embedding_model,
                        "source": (chunk.metadata or {}).get("source"),
                        "language": (chunk.metadata or {}).get("language", "en"),
                        "page_number": (chunk.metadata or {}).get("page_number"),
                        "user_id": (chunk.metadata or {}).get("user_id"),
                        "quality_score": chunk.quality_score or 0.5,
                    },
                )

            postgres_success = True
        except Exception as exc:  # pragma: no cover - surfaced via return
            logger.error("Failed to store chunk in Postgres", exc_info=exc)

        return {
            "pinecone_success": pinecone_success,
            "postgres_success": postgres_success,
        }

    def get_chunk_by_id(self, chunk_id: UUID) -> Chunk | None:
        """Retrieve a chunk from Postgres by its id.

        Returns a `Chunk` instance or None if not found.
        """

        with self.postgres.engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT id,
                           document_id,
                           chunk_index,
                           content,
                           embedding_model,
                           source,
                           language,
                           page_number,
                           user_id,
                           quality_score
                    FROM chunks
                    WHERE id = :id
                    """
                ),
                {"id": str(chunk_id)},
            )
            row = result.fetchone()

        if row is None:
            return None

        metadata = {
            k: v
            for k, v in {
                "source": row.source,
                "language": row.language,
                "page_number": row.page_number,
                "user_id": row.user_id,
            }.items()
            if v is not None
        }

        return Chunk(
            id=UUID(row.id),
            document_id=UUID(row.document_id),
            chunk_index=row.chunk_index,
            content=row.content,
            dense_embedding=[],  # Not stored in Postgres in this story
            sparse_embedding={},
            metadata=metadata,
            quality_score=float(row.quality_score)
            if row.quality_score is not None
            else None,
            embedding_model=row.embedding_model,
            created_at=None,  # Will be defaulted/ignored by consumer
            updated_at=None,
        )

    def batch_store_chunks(self, chunks: Iterable[Chunk]) -> Dict[str, int]:
        """Store multiple chunks and return simple counters."""

        total = 0
        pinecone_ok = 0
        postgres_ok = 0

        for chunk in chunks:
            total += 1
            result = self.store_chunk(chunk)
            if result["pinecone_success"]:
                pinecone_ok += 1
            if result["postgres_success"]:
                postgres_ok += 1

        return {
            "total_chunks": total,
            "pinecone_stored": pinecone_ok,
            "postgres_stored": postgres_ok,
        }
