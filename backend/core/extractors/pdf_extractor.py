"""PDF text extractor for Story 007 / Story 023.

Production-grade PDF extraction using pdfplumber with:
- Table detection and metrics
- Section title heuristics for context-aware chunking
- Extractability ratio for intelligent tier routing
- Encrypted PDF handling
- Confidence scoring based on extraction quality
- Comprehensive error handling and logging
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.core.data_models import ExtractedDocument, ExtractedPage
from backend.core.exceptions import ExtractionError
from backend.core.language_detection import LanguageDetector
from backend.core.logging import get_logger
from backend.core.normalization import TextNormalizer


@dataclass
class PDFExtractionConfig:
    """Configuration for PDF extraction behavior."""

    min_chars_per_page: int = 50
    min_extractability_ratio: float = 0.3
    detect_tables: bool = True
    detect_section_titles: bool = True
    heading_min_font_size: float = 14.0
    password: Optional[str] = None
    max_pages: int = 1000
    timeout_seconds: int = 60


@dataclass
class PDFAnalysisResult:
    """Result of PDF pre-analysis for tier routing."""

    page_count: int = 0
    has_text: bool = False
    has_tables: bool = False
    has_images: bool = False
    extractability_ratio: float = 0.0
    avg_chars_per_page: float = 0.0
    is_encrypted: bool = False
    is_scanned: bool = False
    recommended_tier: int = 1
    analysis_errors: List[str] = field(default_factory=list)


class PDFExtractor:
    """Production-grade PDF text extractor using pdfplumber.

    Features:
    - Per-page extraction with confidence scores
    - Table detection (marks pages with tables for special handling)
    - Heuristic section title detection for context-aware chunking
    - Extractability metrics for intelligent tier routing
    - Encrypted PDF handling with password support
    - Comprehensive error handling with detailed logging
    """

    MIN_CHARS_PER_PAGE = 50

    def __init__(self, config: Optional[PDFExtractionConfig] = None) -> None:
        self._config = config or PDFExtractionConfig()
        self._logger = get_logger("rag.core.pdf_extractor")

    @staticmethod
    def extract(
        content: bytes,
        document_id: UUID,
        filename: str,
        language: Optional[str] = None,
        config: Optional[PDFExtractionConfig] = None,
        password: Optional[str] = None,
    ) -> ExtractedDocument:
        """Extract all pages from a PDF into an ExtractedDocument.

        This static method maintains backward compatibility with existing code.
        For more control, instantiate PDFExtractor with a config and call
        extract_document().
        """
        extractor = PDFExtractor(config)
        return extractor.extract_document(
            content=content,
            document_id=document_id,
            filename=filename,
            language=language,
            password=password,
        )

    def extract_document(
        self,
        content: bytes,
        document_id: UUID,
        filename: str,
        language: Optional[str] = None,
        password: Optional[str] = None,
    ) -> ExtractedDocument:
        """Extract all pages from a PDF into an ExtractedDocument."""
        try:
            import pdfplumber
        except ImportError as exc:
            self._logger.error(
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
                message="pdfplumber is required for PDF extraction; install it via: pip install pdfplumber",
                filename=filename,
                error_type="missing_dependency",
                details={"dependency": "pdfplumber"},
                status_code=500,
            ) from exc

        start_time = time.time()
        effective_password = password or self._config.password

        pdf = self._open_pdf(content, filename, effective_password, pdfplumber)

        pages: List[ExtractedPage] = []
        table_pages = 0
        image_pages = 0
        extractable_pages = 0

        with pdf:
            total_page_count = len(pdf.pages)

            if total_page_count > self._config.max_pages:
                self._logger.warning(
                    "pdf_page_limit_exceeded",
                    extra={
                        "context": {
                            "filename": filename,
                            "total_pages": total_page_count,
                            "max_pages": self._config.max_pages,
                        }
                    },
                )
                total_page_count = self._config.max_pages

            for page_num in range(total_page_count):
                pdf_page = pdf.pages[page_num]
                page_result = self._extract_page(pdf_page, page_num, filename)
                pages.append(page_result["page"])

                if page_result["has_tables"]:
                    table_pages += 1
                if page_result["has_images"]:
                    image_pages += 1
                if not page_result["page"].is_empty:
                    extractable_pages += 1

        # Derive language at document level if not provided.
        sample_text = "\n".join(
            p.normalized_text for p in pages[:3] if p.normalized_text
        )
        doc_language = language or LanguageDetector.detect(sample_text)

        for page in pages:
            if page.language is None:
                page.language = doc_language

        # Document-level quality metrics.
        total_words = sum(p.word_count for p in pages)
        total_chars = sum(p.char_count for p in pages)
        empty_pages = sum(1 for p in pages if p.is_empty)
        non_empty_pages = len(pages) - empty_pages

        extractability_ratio = extractable_pages / len(pages) if pages else 0.0
        avg_chars_per_page = total_chars / len(pages) if pages else 0.0

        # Determine if this looks like a scanned PDF
        is_likely_scanned = extractability_ratio < self._config.min_extractability_ratio

        duration_ms = (time.time() - start_time) * 1000.0

        self._logger.info(
            "pdf_extraction_completed",
            extra={
                "context": {
                    "filename": filename,
                    "document_id": str(document_id),
                    "format": "pdf",
                    "total_pages": len(pages),
                    "extractable_pages": extractable_pages,
                    "table_pages": table_pages,
                    "image_pages": image_pages,
                    "extractability_ratio": round(extractability_ratio, 3),
                    "is_likely_scanned": is_likely_scanned,
                    "language": doc_language,
                    "duration_ms": round(duration_ms, 2),
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
                "extraction_method": "pdfplumber",
                "min_chars_per_page": self._config.min_chars_per_page,
                "total_words": total_words,
                "total_chars": total_chars,
                "empty_pages": empty_pages,
                "non_empty_pages": non_empty_pages,
                "extractable_pages": extractable_pages,
                "table_pages": table_pages,
                "image_pages": image_pages,
                "extractability_ratio": extractability_ratio,
                "avg_chars_per_page": avg_chars_per_page,
                "is_likely_scanned": is_likely_scanned,
            },
            extraction_duration_ms=duration_ms,
        )

    def _open_pdf(
        self,
        content: bytes,
        filename: str,
        password: Optional[str],
        pdfplumber: Any,
    ) -> Any:
        """Open PDF with error handling for corruption and encryption."""
        try:
            pdf = pdfplumber.open(BytesIO(content), password=password)
            return pdf
        except Exception as exc:
            error_str = " ".join(
                [
                    exc.__class__.__name__,
                    str(exc),
                    repr(exc),
                ]
            ).lower()

            # Check for encryption-related errors.
            # pdfplumber frequently raises pdfplumber.utils.exceptions.PdfminerException
            # wrapping pdfminer PDFPasswordIncorrect() when the file is encrypted.
            if (
                "password" in error_str
                or "encrypted" in error_str
                or "pdfpasswordincorrect" in error_str
                or "passwordincorrect" in error_str
            ):
                self._logger.warning(
                    "pdf_encrypted",
                    extra={
                        "context": {
                            "filename": filename,
                            "error_type": "encrypted_file",
                            "password_provided": password is not None,
                        }
                    },
                )
                if password is None:
                    raise ExtractionError(
                        message="PDF is password-protected. Please provide the password.",
                        filename=filename,
                        error_type="encrypted_file",
                        details={"requires_password": True},
                        status_code=400,
                    ) from exc
                else:
                    raise ExtractionError(
                        message="Incorrect password for encrypted PDF.",
                        filename=filename,
                        error_type="invalid_password",
                        details={"password_provided": True},
                        status_code=400,
                    ) from exc

            # Generic corruption/invalid PDF
            self._logger.error(
                "pdf_open_failed",
                extra={
                    "context": {
                        "filename": filename,
                        "error_type": "corrupt_file",
                        "error_message": str(exc)[:200],
                    }
                },
            )
            raise ExtractionError(
                message=f"Failed to open PDF for extraction: {str(exc)[:100]}",
                filename=filename,
                error_type="corrupt_file",
                status_code=500,
            ) from exc

    def _extract_page(
        self,
        pdf_page: Any,
        page_num: int,
        filename: str,
    ) -> Dict[str, Any]:
        """Extract text and metadata from a single page."""
        raw_text = ""
        has_tables = False
        has_images = False
        section_title: Optional[str] = None
        confidence_score = 1.0

        try:
            raw_text = pdf_page.extract_text() or ""
        except Exception as exc:
            self._logger.warning(
                "pdf_page_extraction_error",
                extra={
                    "context": {
                        "filename": filename,
                        "page_number": page_num,
                        "error": str(exc)[:100],
                    }
                },
            )
            confidence_score = 0.0

        normalized_text = TextNormalizer.normalize(raw_text)
        is_empty = TextNormalizer.is_empty_page(normalized_text)
        word_count = len(normalized_text.split()) if normalized_text else 0
        char_count = len(normalized_text)
        line_count = len(raw_text.split("\n")) if raw_text else 0

        # Table detection
        if self._config.detect_tables:
            try:
                tables = pdf_page.extract_tables()
                has_tables = bool(tables and len(tables) > 0)
            except Exception:
                pass

        # Image detection (via presence of image objects)
        try:
            images = getattr(pdf_page, "images", None)
            has_images = bool(images and len(images) > 0)
        except Exception:
            pass

        # Section title detection via font size heuristics
        if self._config.detect_section_titles and not is_empty:
            section_title = self._detect_section_title(pdf_page)

        # Confidence scoring based on extraction quality
        if is_empty:
            confidence_score = 0.0
        elif char_count < self._config.min_chars_per_page:
            confidence_score = 0.5
        elif has_tables:
            # Tables may have extraction artifacts
            confidence_score = 0.9

        page = ExtractedPage(
            page_number=page_num,
            raw_text=raw_text,
            normalized_text=normalized_text,
            is_empty=is_empty,
            word_count=word_count,
            char_count=char_count,
            line_count=line_count,
            language=None,
            section_title=section_title,
            confidence_score=confidence_score,
        )

        return {
            "page": page,
            "has_tables": has_tables,
            "has_images": has_images,
        }

    def _detect_section_title(self, pdf_page: Any) -> Optional[str]:
        """Detect section title using font size heuristics.

        Looks for the first text element with font size above the threshold,
        which often indicates a heading or section title.
        """
        try:
            chars = getattr(pdf_page, "chars", None)
            if not chars:
                return None

            # Group consecutive large chars to form potential heading
            heading_chars: List[str] = []
            current_y: Optional[float] = None

            for char in chars:
                size = char.get("size", 0)
                if size >= self._config.heading_min_font_size:
                    char_y = char.get("top", 0)
                    char_text = char.get("text", "")

                    # Only collect chars from the same line (similar y position)
                    if current_y is None:
                        current_y = char_y
                    elif abs(char_y - current_y) > 5:
                        # Different line, stop collecting
                        break

                    heading_chars.append(char_text)

            if heading_chars:
                title = "".join(heading_chars).strip()
                # Sanity check: title should be reasonable length
                if 3 <= len(title) <= 200:
                    return title

        except Exception:
            pass

        return None

    @classmethod
    def analyze_pdf(
        cls,
        content: bytes,
        filename: str = "document.pdf",
    ) -> PDFAnalysisResult:
        """Analyze PDF characteristics for tier routing decisions.

        This is a lightweight analysis that doesn't do full extraction,
        used to determine which extraction tier to use.
        """
        result = PDFAnalysisResult()
        logger = get_logger("rag.core.pdf_extractor")

        try:
            import pdfplumber
        except ImportError:
            result.analysis_errors.append("pdfplumber not installed")
            result.recommended_tier = 4  # Fall back to OCR
            return result

        try:
            pdf = pdfplumber.open(BytesIO(content))
        except Exception as exc:
            error_str = str(exc).lower()
            if "password" in error_str or "encrypted" in error_str:
                result.is_encrypted = True
                result.analysis_errors.append("PDF is encrypted")
            else:
                result.analysis_errors.append(f"Failed to open: {str(exc)[:50]}")
            result.recommended_tier = 4
            return result

        with pdf:
            result.page_count = len(pdf.pages)
            chars_per_page: List[int] = []

            # Sample pages for analysis (first, middle, last)
            sample_indices = [0]
            if result.page_count > 2:
                sample_indices.append(result.page_count // 2)
            if result.page_count > 1:
                sample_indices.append(result.page_count - 1)

            for idx in sample_indices:
                if idx >= result.page_count:
                    continue

                page = pdf.pages[idx]
                try:
                    text = page.extract_text() or ""
                    char_count = len(text.strip())
                    chars_per_page.append(char_count)

                    if char_count > 100:
                        result.has_text = True

                    tables = page.extract_tables()
                    if tables:
                        result.has_tables = True

                    images = getattr(page, "images", None)
                    if images:
                        result.has_images = True

                except Exception as exc:
                    result.analysis_errors.append(
                        f"Page {idx} analysis failed: {str(exc)[:30]}"
                    )

            # Calculate extractability
            if chars_per_page:
                result.avg_chars_per_page = sum(chars_per_page) / len(chars_per_page)
                extractable_count = sum(1 for c in chars_per_page if c > 50)
                result.extractability_ratio = extractable_count / len(chars_per_page)

            # Determine if scanned
            result.is_scanned = result.extractability_ratio < 0.3

            # Recommend tier based on analysis
            if result.is_scanned:
                result.recommended_tier = 4  # OCR needed
            elif result.has_tables and result.extractability_ratio < 0.7:
                result.recommended_tier = 2  # Complex layout
            elif result.extractability_ratio > 0.9:
                result.recommended_tier = 1  # Simple searchable PDF
            else:
                result.recommended_tier = 2  # Mixed content

        logger.info(
            "pdf_analysis_completed",
            extra={
                "context": {
                    "filename": filename,
                    "page_count": result.page_count,
                    "has_text": result.has_text,
                    "has_tables": result.has_tables,
                    "extractability_ratio": round(result.extractability_ratio, 3),
                    "is_scanned": result.is_scanned,
                    "recommended_tier": result.recommended_tier,
                }
            },
        )

        return result
