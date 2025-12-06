"""Plain text extractor for Story 007.

Converts raw text bytes into an ExtractedDocument using line-based paging
and text normalization.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from backend.core.data_models import ExtractedDocument, ExtractedPage
from backend.core.exceptions import ExtractionError
from backend.core.language_detection import LanguageDetector
from backend.core.logging import get_logger
from backend.core.normalization import TextNormalizer


class TextExtractor:
    """Extracts text from plain text files."""

    LINES_PER_PAGE = 50

    @staticmethod
    def _decode(content: bytes) -> str:
        """Decode bytes into text, trying common encodings.

        Falls back to UTF-8 with errors ignored if necessary.
        """

        for encoding in ("utf-8", "latin-1"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue

        try:
            return content.decode("utf-8", errors="ignore")
        except Exception as exc:  # pragma: no cover - very defensive
            logger = get_logger("rag.core.text_extractor")
            logger.error(
                "text_decode_failed",
                extra={
                    "context": {
                        "error_type": "decode_error",
                        "encodings_tried": ["utf-8", "latin-1"],
                    }
                },
            )

            raise ExtractionError(
                message="Failed to decode text content",
                filename="<in-memory>",
                error_type="decode_error",
                details={"encodings_tried": ["utf-8", "latin-1"]},
                status_code=500,
            ) from exc

    @classmethod
    def extract(
        cls,
        content: bytes,
        document_id: UUID,
        filename: str,
    ) -> ExtractedDocument:
        """Extract text from bytes into an ExtractedDocument.

        Splits content into pages based on line count and applies
        normalization to each page.
        """

        import time

        logger = get_logger("rag.core.text_extractor")
        start_time = time.time()

        decoded = cls._decode(content)
        # Normalize line endings first.
        decoded = decoded.replace("\r\n", "\n").replace("\r", "\n")
        lines = decoded.split("\n")

        pages: List[ExtractedPage] = []
        for page_index in range(0, len(lines), cls.LINES_PER_PAGE):
            page_lines = lines[page_index : page_index + cls.LINES_PER_PAGE]
            raw_text = "\n".join(page_lines)
            normalized_text = TextNormalizer.normalize(raw_text)

            is_empty = TextNormalizer.is_empty_page(normalized_text)
            word_count = len(normalized_text.split()) if normalized_text else 0
            char_count = len(normalized_text)
            line_count = len(page_lines)

            pages.append(
                ExtractedPage(
                    page_number=page_index // cls.LINES_PER_PAGE,
                    raw_text=raw_text,
                    normalized_text=normalized_text,
                    is_empty=is_empty,
                    word_count=word_count,
                    char_count=char_count,
                    line_count=line_count,
                    language=None,
                    section_title=None,
                    confidence_score=1.0,
                )
            )

        # Determine language at document level from concatenated normalized text.
        full_text = "\n".join(p.normalized_text for p in pages)
        language = LanguageDetector.detect(full_text or decoded)

        # Populate per-page language for convenience.
        for page in pages:
            page.language = language

        # Document-level quality metrics.
        total_words = sum(p.word_count for p in pages)
        total_chars = sum(p.char_count for p in pages)
        empty_pages = sum(1 for p in pages if p.is_empty)
        non_empty_pages = len(pages) - empty_pages

        duration_ms = (time.time() - start_time) * 1000.0

        logger.info(
            "text_extraction_completed",
            extra={
                "context": {
                    "filename": filename,
                    "document_id": str(document_id),
                    "format": "txt",
                    "total_pages": len(pages),
                    "language": language,
                    "duration_ms": duration_ms,
                }
            },
        )

        return ExtractedDocument(
            document_id=document_id,
            filename=filename,
            format="txt",
            language=language,
            total_pages=len(pages),
            pages=pages,
            extraction_metadata={
                "lines_per_page": cls.LINES_PER_PAGE,
                "total_words": total_words,
                "total_chars": total_chars,
                "empty_pages": empty_pages,
                "non_empty_pages": non_empty_pages,
            },
            extraction_duration_ms=duration_ms,
        )
