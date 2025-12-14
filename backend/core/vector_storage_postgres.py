from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text

from backend.core.embedding_models import Embedding
from backend.core.vector_storage import VectorDBStorageLayer
from backend.data_layer.postgres_client import PostgresClient


class PostgresVectorDBStorageLayer(VectorDBStorageLayer):
    def __init__(self, postgres_client: PostgresClient | None = None) -> None:
        self._postgres = postgres_client or PostgresClient()

    @staticmethod
    def _to_pgvector_literal(vector: List[float]) -> str:
        return "[" + ",".join(str(float(x)) for x in vector) + "]"

    @staticmethod
    def _parse_pgvector(value: Any) -> List[float]:
        if value is None:
            return []
        if isinstance(value, list):
            return [float(x) for x in value]
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("[") and raw.endswith("]"):
                inner = raw[1:-1].strip()
                if not inner:
                    return []
                return [float(x) for x in inner.split(",")]
        return []

    @staticmethod
    def _build_metadata_from_row(row: Any) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        source = getattr(row, "source", None)
        if source is not None:
            metadata["source"] = source
        document_type = getattr(row, "document_type", None)
        if document_type is not None:
            metadata["document_type"] = document_type
        language = getattr(row, "language", None)
        if language is not None:
            metadata["language"] = language
        page_number = getattr(row, "page_number", None)
        if page_number is not None:
            metadata["page_number"] = page_number
        section_title = getattr(row, "section_title", None)
        if section_title is not None:
            metadata["section_title"] = section_title
        user_id = getattr(row, "user_id", None)
        if user_id is not None:
            metadata["user_id"] = user_id
        return metadata

    async def store_embedding(self, embedding: Embedding) -> bool:
        result = await self.store_embeddings_batch([embedding])
        return int(result.get("stored_count", 0)) == 1

    async def store_embeddings_batch(
        self, embeddings: List[Embedding]
    ) -> Dict[str, Any]:
        if not embeddings:
            return {
                "stored_count": 0,
                "failed_count": 0,
                "failures": [],
            }

        failures: List[Dict[str, Any]] = []

        # Assign chunk_index per document_id in this batch (required by schema).
        index_by_doc: Dict[UUID, int] = {}

        with self._postgres.engine.begin() as conn:
            for emb in embeddings:
                try:
                    metadata = emb.metadata or {}

                    chunk_index_raw = metadata.get("chunk_index")
                    if chunk_index_raw is None:
                        chunk_index = index_by_doc.get(emb.document_id, 0)
                        index_by_doc[emb.document_id] = chunk_index + 1
                    else:
                        chunk_index = int(chunk_index_raw)
                    source = (
                        metadata.get("source")
                        or metadata.get("source_filename")
                        or metadata.get("filename")
                        or None
                    )

                    language = metadata.get("language")
                    document_type = metadata.get("document_type")
                    page_number = metadata.get("page_number")
                    section_title = metadata.get("section_title")
                    user_id = metadata.get("user_id") or "anonymous"

                    quality_score = float(emb.quality_score or 0.0)

                    conn.execute(
                        text(
                            """
                            INSERT INTO documents (id, filename)
                            VALUES (:doc_id, :filename)
                            ON CONFLICT (id) DO NOTHING
                            """
                        ),
                        {
                            "doc_id": str(emb.document_id),
                            "filename": str(source or "unknown"),
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
                                original_content,
                                embedding_model,
                                dense_embedding,
                                source,
                                document_type,
                                language,
                                page_number,
                                section_title,
                                user_id,
                                quality_score,
                                is_duplicate
                            ) VALUES (
                                :id,
                                :document_id,
                                :chunk_index,
                                :content,
                                :original_content,
                                :embedding_model,
                                CAST(:dense_embedding AS vector),
                                :source,
                                :document_type,
                                :language,
                                :page_number,
                                :section_title,
                                :user_id,
                                :quality_score,
                                :is_duplicate
                            )
                            ON CONFLICT (id) DO UPDATE SET
                                content = EXCLUDED.content,
                                original_content = EXCLUDED.original_content,
                                embedding_model = EXCLUDED.embedding_model,
                                dense_embedding = EXCLUDED.dense_embedding,
                                source = EXCLUDED.source,
                                document_type = EXCLUDED.document_type,
                                language = EXCLUDED.language,
                                page_number = EXCLUDED.page_number,
                                section_title = EXCLUDED.section_title,
                                user_id = EXCLUDED.user_id,
                                quality_score = EXCLUDED.quality_score,
                                is_duplicate = EXCLUDED.is_duplicate,
                                embedding_generated_at = NOW()
                            """
                        ),
                        {
                            "id": str(emb.chunk_id),
                            "document_id": str(emb.document_id),
                            "chunk_index": int(chunk_index),
                            "content": emb.content,
                            "original_content": emb.content,
                            "embedding_model": emb.embedding_model,
                            "dense_embedding": self._to_pgvector_literal(emb.embedding),
                            "source": source,
                            "document_type": document_type,
                            "language": language,
                            "page_number": page_number,
                            "section_title": section_title,
                            "user_id": user_id,
                            "quality_score": quality_score,
                            "is_duplicate": bool(getattr(emb, "is_duplicate", False)),
                        },
                    )
                except Exception as exc:  # pragma: no cover
                    failures.append(
                        {
                            "chunk_id": str(emb.chunk_id),
                            "error": str(exc),
                        }
                    )

        stored_count = max(0, len(embeddings) - len(failures))
        return {
            "stored_count": stored_count,
            "failed_count": len(failures),
            "failures": failures,
        }

    async def search_by_similarity(
        self,
        embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Embedding]:
        if not embedding:
            return []

        filters = filters or {}
        where_clauses: List[str] = ["dense_embedding IS NOT NULL"]
        params: Dict[str, Any] = {
            "query_vec": self._to_pgvector_literal(embedding),
            "top_k": int(top_k),
        }

        # Simple metadata filters supported by schema columns.
        for key in (
            "document_id",
            "user_id",
            "document_type",
            "language",
            "page_number",
        ):
            if key in filters:
                where_clauses.append(f"{key} = :{key}")
                params[key] = filters[key]

        where_sql = " AND ".join(where_clauses)

        # Use cosine distance (<=>) to align with in-memory cosine similarity.
        query = text(
            f"""
            SELECT
                id,
                document_id,
                content,
                dense_embedding,
                embedding_model,
                quality_score,
                is_duplicate,
                source,
                document_type,
                language,
                page_number,
                section_title,
                user_id,
                created_at,
                updated_at
            FROM chunks
            WHERE {where_sql}
            ORDER BY dense_embedding <=> CAST(:query_vec AS vector)
            LIMIT :top_k
            """
        )

        with self._postgres.engine.connect() as conn:
            rows = conn.execute(query, params).fetchall()

        results: List[Embedding] = []
        for row in rows:
            vec = self._parse_pgvector(getattr(row, "dense_embedding", None))
            results.append(
                Embedding(
                    chunk_id=UUID(str(row.id)),
                    document_id=UUID(str(row.document_id)),
                    content=str(row.content),
                    embedding=vec,
                    embedding_model=str(
                        getattr(row, "embedding_model", "text-embedding-3-small")
                    ),
                    embedding_dimension=len(vec) or 1536,
                    metadata=self._build_metadata_from_row(row),
                    quality_score=float(getattr(row, "quality_score", 0.0) or 0.0),
                )
            )

        return results

    async def search_by_document(self, document_id: UUID) -> List[Embedding]:
        with self._postgres.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        id,
                        document_id,
                        content,
                        dense_embedding,
                        embedding_model,
                        quality_score,
                        is_duplicate,
                        source,
                        document_type,
                        language,
                        page_number,
                        section_title,
                        user_id,
                        created_at,
                        updated_at
                    FROM chunks
                    WHERE document_id = :document_id
                      AND dense_embedding IS NOT NULL
                    ORDER BY chunk_index ASC
                    """
                ),
                {"document_id": str(document_id)},
            ).fetchall()

        results: List[Embedding] = []
        for row in rows:
            vec = self._parse_pgvector(getattr(row, "dense_embedding", None))
            results.append(
                Embedding(
                    chunk_id=UUID(str(row.id)),
                    document_id=UUID(str(row.document_id)),
                    content=str(row.content),
                    embedding=vec,
                    embedding_model=str(
                        getattr(row, "embedding_model", "text-embedding-3-small")
                    ),
                    embedding_dimension=len(vec) or 1536,
                    metadata=self._build_metadata_from_row(row),
                    quality_score=float(getattr(row, "quality_score", 0.0) or 0.0),
                )
            )

        return results

    async def check_duplicate_content(self, content: str) -> Optional[Embedding]:
        if not content:
            return None

        with self._postgres.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                        id,
                        document_id,
                        content,
                        dense_embedding,
                        embedding_model,
                        quality_score,
                        is_duplicate,
                        source,
                        document_type,
                        language,
                        page_number,
                        section_title,
                        user_id,
                        created_at,
                        updated_at
                    FROM chunks
                    WHERE content = :content
                      AND dense_embedding IS NOT NULL
                    LIMIT 1
                    """
                ),
                {"content": content},
            ).fetchone()

        if row is None:
            return None

        vec = self._parse_pgvector(getattr(row, "dense_embedding", None))
        return Embedding(
            chunk_id=UUID(str(row.id)),
            document_id=UUID(str(row.document_id)),
            content=str(row.content),
            embedding=vec,
            embedding_model=str(
                getattr(row, "embedding_model", "text-embedding-3-small")
            ),
            embedding_dimension=len(vec) or 1536,
            metadata=self._build_metadata_from_row(row),
            quality_score=float(getattr(row, "quality_score", 0.0) or 0.0),
        )
