"""Chunking service orchestrator over ExtractedDocument (Story 008)."""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from backend.core.chunkers.recursive_chunker import RecursiveChunker
from backend.core.chunkers.sliding_window_chunker import SlidingWindowChunker
from backend.core.chunking_metadata import ChunkMetadataTracker
from backend.core.chunking_models import Chunk, ChunkingConfig, ChunkingResult
from backend.core.data_models import ExtractedDocument
from backend.core.logging import get_logger


class ChunkingService:
    """Main chunking orchestration over an ``ExtractedDocument``."""

    def __init__(
        self,
        *,
        sliding_chunker: Optional[SlidingWindowChunker] = None,
        recursive_chunker: Optional[RecursiveChunker] = None,
    ) -> None:
        self._sliding_chunker = sliding_chunker or SlidingWindowChunker()
        self._recursive_chunker = recursive_chunker or RecursiveChunker()
        self._logger = get_logger("rag.core.chunking_service")

    def chunk_document(
        self,
        extracted_document: ExtractedDocument,
        config: ChunkingConfig,
        trace_context: Optional[Dict[str, str]] = None,
    ) -> ChunkingResult:
        """Chunk an ``ExtractedDocument`` into retrieval-friendly units."""

        trace_context = trace_context or {}
        logger = self._logger

        logger.info(
            "chunking_started",
            extra={
                "context": {
                    "document_id": str(extracted_document.document_id),
                    "strategy": config.strategy,
                    "trace_context": trace_context,
                }
            },
        )

        start_time = time.time()
        chunks: List[Chunk] = []
        empty_chunks_discarded = 0

        for page in extracted_document.pages:
            if page.is_empty or not page.normalized_text.strip():
                continue

            page_text = page.normalized_text

            if config.strategy == "sliding_window":
                raw_chunks = self._sliding_chunker.chunk(
                    text=page_text,
                    chunk_size=config.chunk_size_chars,
                    overlap=config.chunk_overlap_chars,
                )
            elif config.strategy == "recursive":
                raw_chunks = self._recursive_chunker.chunk(
                    text=page_text,
                    chunk_size=config.chunk_size_chars,
                    separators=config.separators,
                    keep_separator=config.keep_separator,
                )
            else:
                raise ValueError(f"Unsupported chunking strategy: {config.strategy}")

            for raw in raw_chunks:
                content = str(raw["content"])
                start_offset = int(raw["start"])
                end_offset = int(raw["end"])

                # Apply min/max size constraints.
                if len(content) < config.min_chunk_size_chars:
                    empty_chunks_discarded += 1
                    continue

                if len(content) > config.max_chunk_size_chars:
                    content = content[: config.max_chunk_size_chars]
                    end_offset = start_offset + len(content)

                chunk = ChunkMetadataTracker.create_chunk(
                    content=content,
                    document_id=extracted_document.document_id,
                    page_number=page.page_number,
                    position_in_page={"start": start_offset, "end": end_offset},
                    section_title=page.section_title,
                    original_content=content,
                    document_type=extracted_document.format,
                    source_filename=extracted_document.filename,
                    language=page.language or extracted_document.language,
                )

                chunks.append(chunk)

        duration_ms = (time.time() - start_time) * 1000.0

        total_chunks = len(chunks)
        total_chars = sum(c.char_count for c in chunks)
        total_tokens = sum(c.token_count for c in chunks)
        avg_chunk_size_chars = (
            float(total_chars) / total_chunks if total_chunks else 0.0
        )

        quality_metrics: Dict[str, object] = {
            "avg_chunk_size_chars": avg_chunk_size_chars,
            "total_tokens_across_chunks": total_tokens,
            "total_chunks": total_chunks,
            "empty_chunks_discarded": empty_chunks_discarded,
        }

        logger.info(
            "chunking_completed",
            extra={
                "context": {
                    "document_id": str(extracted_document.document_id),
                    "strategy": config.strategy,
                    "duration_ms": duration_ms,
                    "total_chunks": total_chunks,
                }
            },
        )

        return ChunkingResult(
            document_id=extracted_document.document_id,
            total_chunks=total_chunks,
            chunks=chunks,
            chunking_config=config,
            chunking_duration_ms=duration_ms,
            quality_metrics=quality_metrics,
        )
