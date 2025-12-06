"""PDF text extractor for Story 007.

Uses pdfplumber (if available) to extract text page by page into an
ExtractedDocument. If pdfplumber is not installed, this module should be
updated accordingly; the tests assume it is present per the story spec.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from backend.core.data_models import ExtractedDocument, ExtractedPage
from backend.core.exceptions import ExtractionError
from backend.core.language_detection import LanguageDetector
from backend.core.logging import get_logger
from backend.core.normalization import TextNormalizer


class PDFExtractor:
    """Extracts text from PDF files page by page."""

    MIN_CHARS_PER_PAGE = 50

    @staticmethod
    def extract(
        content: bytes,
        document_id: UUID,
        filename: str,
        language: Optional[str] = None,
    ) -> ExtractedDocument:
        """Extract all pages from a PDF into an ExtractedDocument."""

        import time
        from io import BytesIO

        logger = get_logger("rag.core.pdf_extractor")

        try:
            import pdfplumber  # type: ignore[import-not-found]
        except (
            ImportError
        ) as exc:  # pragma: no cover - exercised only without dependency
            logger.error(
                "pdfplumber_missing",
                extra={
                    "context": {
                        "filename": filename,
                        "error_type": "missing_dependency",
                        "dependency": "pdfplumber",
                    }
                },
            )
            raise ExtractionError(
                message=(
                    "pdfplumber is required for PDF extraction; install it to use PDFExtractor."
                ),
                filename=filename,
                error_type="missing_dependency",
                details={"dependency": "pdfplumber"},
                status_code=500,
            ) from exc

        start_time = time.time()
        pages: List[ExtractedPage] = []

        # pdfplumber expects a file-like object; wrap bytes via BytesIO.
        try:
            pdf = pdfplumber.open(BytesIO(content))
        except Exception as exc:  # pragma: no cover - corrupt/invalid PDFs
            logger.error(
                "pdf_open_failed",
                extra={
                    "context": {
                        "filename": filename,
                        "error_type": "corrupt_file",
                    }
                },
            )
            raise ExtractionError(
                message="Failed to open PDF for extraction",
                filename=filename,
                error_type="corrupt_file",
                status_code=500,
            ) from exc

        with pdf:
            for page_num, pdf_page in enumerate(pdf.pages):
                raw_text = pdf_page.extract_text() or ""
                normalized_text = TextNormalizer.normalize(raw_text)

                is_empty = TextNormalizer.is_empty_page(normalized_text)
                word_count = len(normalized_text.split()) if normalized_text else 0
                char_count = len(normalized_text)
                line_count = len(raw_text.split("\n")) if raw_text else 0

                pages.append(
                    ExtractedPage(
                        page_number=page_num,
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

        # Derive language at document level if not provided.
        full_text = "\n".join(p.normalized_text for p in pages)
        doc_language = language or LanguageDetector.detect(full_text)

        for page in pages:
            page.language = doc_language

        # Document-level quality metrics.
        total_words = sum(p.word_count for p in pages)
        total_chars = sum(p.char_count for p in pages)
        empty_pages = sum(1 for p in pages if p.is_empty)
        non_empty_pages = len(pages) - empty_pages

        duration_ms = (time.time() - start_time) * 1000.0

        logger.info(
            "pdf_extraction_completed",
            extra={
                "context": {
                    "filename": filename,
                    "document_id": str(document_id),
                    "format": "pdf",
                    "total_pages": len(pages),
                    "language": doc_language,
                    "duration_ms": duration_ms,
                }
            },
        )

        return ExtractedDocument(
            document_id=document_id,
            filename=filename,
            format="pdf",
            language=doc_language,
            total_pages=len(pages),
            pages=pages,
            extraction_metadata={
                "min_chars_per_page": PDFExtractor.MIN_CHARS_PER_PAGE,
                "total_words": total_words,
                "total_chars": total_chars,
                "empty_pages": empty_pages,
                "non_empty_pages": non_empty_pages,
            },
            extraction_duration_ms=duration_ms,
        )
