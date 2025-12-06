"""High-level text extraction service for Story 007.

Provides a single entrypoint that takes a filename, raw bytes, and a
`document_id`, detects the format, and routes to the appropriate
extractor to produce an `ExtractedDocument`.
"""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from backend.core.data_models import ExtractedDocument
from backend.core.extractors.markdown_extractor import MarkdownExtractor
from backend.core.extractors.pdf_extractor import PDFExtractor
from backend.core.extractors.text_extractor import TextExtractor
from backend.core.format_detector import FileFormat, FormatDetector
from backend.core.logging import get_logger


class TextExtractionService:
    """Facade over format detection and concrete extractors."""

    def __init__(self, detector: FormatDetector | None = None) -> None:
        self._detector = detector or FormatDetector()

    def extract(
        self, filename: str, content: bytes, document_id: UUID
    ) -> ExtractedDocument:
        """Detect format and extract into an `ExtractedDocument`.

        Raises ValueError if the file format is unsupported.
        """

        logger = get_logger("rag.core.text_extraction_service")

        logger.info(
            "extraction_started",
            extra={
                "context": {
                    "filename": filename,
                    "document_id": str(document_id),
                }
            },
        )

        fmt = self._detector.detect_format(filename, content)

        if fmt == FileFormat.PDF:
            extractor: Callable[..., ExtractedDocument] = PDFExtractor.extract
        elif fmt == FileFormat.TEXT:
            extractor = TextExtractor.extract
        elif fmt == FileFormat.MARKDOWN:
            extractor = MarkdownExtractor.extract
        else:  # pragma: no cover - defensive branch
            # FormatDetector should already have raised ExtractionError for
            # unsupported formats, so reaching this branch would indicate an
            # internal mismatch.
            logger.error(
                "extraction_unsupported_format_internal",
                extra={
                    "context": {
                        "filename": filename,
                        "document_id": str(document_id),
                        "format": str(fmt),
                    }
                },
            )
            raise ValueError(f"Unsupported file format: {fmt}")

        result = extractor(content=content, document_id=document_id, filename=filename)

        logger.info(
            "extraction_completed",
            extra={
                "context": {
                    "filename": filename,
                    "document_id": str(document_id),
                    "format": result.format,
                    "total_pages": result.total_pages,
                    "duration_ms": result.extraction_duration_ms,
                }
            },
        )

        return result
