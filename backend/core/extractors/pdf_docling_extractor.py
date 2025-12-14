"""Tier 2: Docling-based PDF extraction (Story 023).

Uses Docling's DocumentConverter and export helpers to extract page-aware
markdown/text from complex PDFs.
"""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from backend.core.data_models import ExtractedDocument, ExtractedPage
from backend.core.exceptions import ExtractionError
from backend.core.language_detection import LanguageDetector
from backend.core.logging import get_logger
from backend.core.normalization import TextNormalizer


@dataclass
class PDFDoclingConfig:
    timeout_seconds: int = 60
    max_pages: int = 1000


class PDFDoclingExtractor:
    def __init__(self, config: Optional[PDFDoclingConfig] = None) -> None:
        self._config = config or PDFDoclingConfig()
        self._logger = get_logger("rag.core.pdf_docling_extractor")

    @staticmethod
    def _guess_section_title_from_markdown(markdown: str) -> Optional[str]:
        for line in (markdown or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()[:200] or None
            break
        return None

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

        # Password handling is not supported via this integration.
        if password is not None:
            raise ExtractionError(
                message="Password-protected PDFs are not supported by Docling tier in this pipeline",
                filename=filename,
                error_type="invalid_configuration",
                details={"tier": 2, "password_provided": True},
                status_code=400,
            )

        try:
            from docling.document_converter import DocumentConverter
        except Exception as exc:
            raise ExtractionError(
                message="docling is required for Tier 2 extraction; install it via: pip install docling",
                filename=filename,
                error_type="missing_dependency",
                details={"dependency": "docling", "error": str(exc)[:200]},
                status_code=500,
            ) from exc

        try:
            from docling.utils.export import generate_multimodal_pages
        except Exception as exc:
            raise ExtractionError(
                message="docling export utilities are unavailable; docling install may be corrupted",
                filename=filename,
                error_type="missing_dependency",
                details={"dependency": "docling", "module": "docling.utils.export"},
                status_code=500,
            ) from exc

        start_time = time.time()

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / filename
            if pdf_path.suffix.lower() != ".pdf":
                pdf_path = pdf_path.with_suffix(".pdf")
            pdf_path.write_bytes(content)

            converter = DocumentConverter()

            try:
                conversion = converter.convert(
                    source=pdf_path,
                    raises_on_error=True,
                    max_num_pages=self._config.max_pages,
                )
            except Exception as exc:
                raise ExtractionError(
                    message=f"Docling conversion failed: {str(exc)[:160]}",
                    filename=filename,
                    error_type="docling_failed",
                    status_code=500,
                ) from exc

            pages: List[ExtractedPage] = []

            try:
                for (
                    content_text,
                    content_md,
                    content_dt,
                    page_cells,
                    page_segments,
                    page,
                ) in generate_multimodal_pages(conversion):
                    _ = content_dt

                    raw_text = content_md or content_text or ""
                    normalized = TextNormalizer.normalize(raw_text)
                    is_empty = not normalized.strip()

                    section_title = self._guess_section_title_from_markdown(
                        content_md or ""
                    )

                    pages.append(
                        ExtractedPage(
                            page_number=int(getattr(page, "page_no", len(pages) + 1)),
                            raw_text=raw_text,
                            normalized_text=normalized,
                            is_empty=is_empty,
                            word_count=len(normalized.split()) if normalized else 0,
                            char_count=len(normalized),
                            line_count=len(
                                [ln for ln in normalized.splitlines() if ln.strip()]
                            ),
                            language=None,
                            section_title=section_title,
                            confidence_score=0.85 if not is_empty else 0.0,
                        )
                    )

                    elapsed = time.time() - start_time
                    if elapsed > float(self._config.timeout_seconds):
                        raise ExtractionError(
                            message=f"Docling extraction timed out after {self._config.timeout_seconds}s",
                            filename=filename,
                            error_type="timeout",
                            details={
                                "timeout_seconds": self._config.timeout_seconds,
                                "tier": 2,
                            },
                            status_code=408,
                        )
            except ExtractionError:
                raise
            except Exception as exc:
                raise ExtractionError(
                    message=f"Docling export failed: {str(exc)[:160]}",
                    filename=filename,
                    error_type="docling_export_failed",
                    status_code=500,
                ) from exc

            if not pages:
                raise ExtractionError(
                    message="Docling produced no pages",
                    filename=filename,
                    error_type="empty_extraction",
                    details={"tier": 2},
                    status_code=500,
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
                "pdf_docling_extraction_completed",
                extra={
                    "context": {
                        "filename": filename,
                        "document_id": str(document_id),
                        "total_pages": len(pages),
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
                    "extraction_method": "docling",
                    "tier": 2,
                    "max_pages": self._config.max_pages,
                },
                extraction_duration_ms=duration_ms,
            )
