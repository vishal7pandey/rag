"""Tier 4: OCR-based PDF extraction (Story 023).

Uses pypdfium2 to render pages to images and pytesseract to OCR them.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from backend.core.data_models import ExtractedDocument, ExtractedPage
from backend.core.exceptions import ExtractionError
from backend.core.language_detection import LanguageDetector
from backend.core.logging import get_logger
from backend.core.normalization import TextNormalizer


@dataclass
class PDFOCRConfig:
    dpi: int = 300
    lang: str = "eng"
    timeout_seconds: int = 120
    tesseract_cmd: Optional[str] = None
    max_pages: int = 1000


class PDFOCRExtractor:
    def __init__(self, config: Optional[PDFOCRConfig] = None) -> None:
        self._config = config or PDFOCRConfig()
        self._logger = get_logger("rag.core.pdf_ocr_extractor")

    @staticmethod
    def _default_tesseract_cmd() -> Optional[str]:
        # Common Windows install path.
        candidate = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
        if os.path.exists(candidate):
            return candidate
        return None

    def _resolve_tesseract_cmd(self) -> Optional[str]:
        cmd = (
            self._config.tesseract_cmd
            or os.getenv("TESSERACT_CMD")
            or self._default_tesseract_cmd()
        )
        return cmd

    def _configure_tesseract(self, *, filename: str) -> Optional[str]:
        try:
            import pytesseract
        except ImportError as exc:
            raise ExtractionError(
                message="pytesseract is required for OCR extraction; install it via: pip install pytesseract",
                filename=filename,
                error_type="missing_dependency",
                details={"dependency": "pytesseract"},
                status_code=500,
            ) from exc

        cmd = self._resolve_tesseract_cmd()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd

        # Verify we can run tesseract.
        try:
            _ = pytesseract.get_tesseract_version()
        except Exception as exc:
            raise ExtractionError(
                message="Tesseract OCR is not available. Install tesseract and/or set TESSERACT_CMD.",
                filename=filename,
                error_type="dependency_not_available",
                details={"dependency": "tesseract", "error": str(exc)[:200]},
                status_code=500,
            ) from exc

        return cmd

    def extract_document(
        self,
        *,
        content: bytes,
        document_id: UUID,
        filename: str,
        language: Optional[str] = None,
        password: Optional[str] = None,
    ) -> ExtractedDocument:
        if not content:
            raise ExtractionError(
                message="Empty file content",
                filename=filename,
                error_type="empty_content",
                status_code=400,
            )

        # We ignore password here; OCR happens on rendered pages.
        _ = password

        try:
            import pypdfium2 as pdfium
        except ImportError as exc:
            raise ExtractionError(
                message="pypdfium2 is required for OCR extraction; install it via: pip install pypdfium2",
                filename=filename,
                error_type="missing_dependency",
                details={"dependency": "pypdfium2"},
                status_code=500,
            ) from exc

        try:
            import pytesseract
        except ImportError as exc:
            raise ExtractionError(
                message="pytesseract is required for OCR extraction; install it via: pip install pytesseract",
                filename=filename,
                error_type="missing_dependency",
                details={"dependency": "pytesseract"},
                status_code=500,
            ) from exc

        resolved_cmd = self._configure_tesseract(filename=filename)

        start_time = time.time()
        pages: List[ExtractedPage] = []

        try:
            pdf = pdfium.PdfDocument(content)
        except Exception as exc:
            raise ExtractionError(
                message=f"Failed to open PDF for OCR: {str(exc)[:120]}",
                filename=filename,
                error_type="corrupt_file",
                status_code=500,
            ) from exc

        page_count = min(len(pdf), self._config.max_pages)

        for i in range(page_count):
            elapsed = time.time() - start_time
            if elapsed > float(self._config.timeout_seconds):
                raise ExtractionError(
                    message=f"OCR timed out after {self._config.timeout_seconds}s",
                    filename=filename,
                    error_type="timeout",
                    details={"timeout_seconds": self._config.timeout_seconds},
                    status_code=408,
                )

            try:
                page = pdf[i]
                # Scale to DPI (pdfium uses 72 DPI units).
                scale = float(self._config.dpi) / 72.0
                bitmap = page.render(scale=scale)
                pil_image = bitmap.to_pil()

                text = pytesseract.image_to_string(pil_image, lang=self._config.lang)
            except ExtractionError:
                raise
            except Exception as exc:
                raise ExtractionError(
                    message=f"OCR failed on page {i + 1}: {str(exc)[:120]}",
                    filename=filename,
                    error_type="ocr_failed",
                    details={"page_number": i + 1},
                    status_code=500,
                ) from exc

            normalized = TextNormalizer.normalize(text or "")
            is_empty = not normalized.strip()

            pages.append(
                ExtractedPage(
                    page_number=i + 1,
                    raw_text=text or "",
                    normalized_text=normalized,
                    is_empty=is_empty,
                    word_count=len(normalized.split()) if normalized else 0,
                    char_count=len(normalized),
                    line_count=len(
                        [ln for ln in normalized.splitlines() if ln.strip()]
                    ),
                    language=None,
                    section_title=None,
                    confidence_score=0.6 if not is_empty else 0.0,
                )
            )

        sample_text = "\n".join(
            p.normalized_text for p in pages[:3] if p.normalized_text
        )
        doc_language = language or LanguageDetector.detect(sample_text)
        for p in pages:
            if p.language is None:
                p.language = doc_language

        duration_ms = (time.time() - start_time) * 1000.0

        self._logger.info(
            "pdf_ocr_extraction_completed",
            extra={
                "context": {
                    "filename": filename,
                    "document_id": str(document_id),
                    "total_pages": len(pages),
                    "dpi": self._config.dpi,
                    "lang": self._config.lang,
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
                "extraction_method": "tesseract_ocr",
                "dpi": self._config.dpi,
                "lang": self._config.lang,
                "tesseract_cmd": resolved_cmd,
            },
            extraction_duration_ms=duration_ms,
        )
