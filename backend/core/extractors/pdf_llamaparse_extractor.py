"""Tier 3: LlamaParse-based PDF extraction (Story 023).

Uses LlamaParse via llama-cloud-services (LlamaCloud).
"""

from __future__ import annotations

import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
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
class PDFLlamaParseConfig:
    api_key: Optional[str] = None
    timeout_seconds: int = 120
    max_pages: int = 1000


class PDFLlamaParseExtractor:
    def __init__(self, config: Optional[PDFLlamaParseConfig] = None) -> None:
        self._config = config or PDFLlamaParseConfig()
        self._logger = get_logger("rag.core.pdf_llamaparse_extractor")

    def _resolve_api_key(self) -> Optional[str]:
        return self._config.api_key or os.getenv("LLAMA_CLOUD_API_KEY")

    @staticmethod
    def _documents_to_text(documents: object) -> str:
        if documents is None:
            return ""

        if isinstance(documents, (list, tuple)):
            parts: List[str] = []
            for d in documents:
                parts.append(PDFLlamaParseExtractor._documents_to_text(d))
            return "\n\n".join([p for p in parts if p.strip()])

        # LlamaIndex Document-like
        for attr in ("text", "content"):
            if hasattr(documents, attr):
                val = getattr(documents, attr)
                if isinstance(val, str):
                    return val

        for method in ("get_text", "get_content"):
            if hasattr(documents, method):
                try:
                    val = getattr(documents, method)()
                    if isinstance(val, str):
                        return val
                except Exception:
                    pass

        return str(documents)

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

        if password is not None:
            raise ExtractionError(
                message="Password-protected PDFs are not supported by LlamaParse tier in this pipeline",
                filename=filename,
                error_type="invalid_configuration",
                details={"tier": 3, "password_provided": True},
                status_code=400,
            )

        api_key = self._resolve_api_key()
        if not api_key:
            raise ExtractionError(
                message="LLAMA_CLOUD_API_KEY is required to use Tier 3 (LlamaParse)",
                filename=filename,
                error_type="missing_api_key",
                details={"tier": 3, "env": "LLAMA_CLOUD_API_KEY"},
                status_code=400,
            )

        try:
            from llama_cloud_services import LlamaParse
        except ImportError as exc:
            raise ExtractionError(
                message="llama-cloud-services is required for Tier 3 extraction; install it via: pip install llama-cloud-services",
                filename=filename,
                error_type="missing_dependency",
                details={"dependency": "llama-cloud-services"},
                status_code=500,
            ) from exc

        start_time = time.time()

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / filename
            if pdf_path.suffix.lower() != ".pdf":
                pdf_path = pdf_path.with_suffix(".pdf")
            pdf_path.write_bytes(content)

            parser = LlamaParse(api_key=api_key, verbose=False)

            def _do_parse() -> object:
                return parser.load_data(str(pdf_path))

            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_do_parse)
                    documents = future.result(
                        timeout=float(self._config.timeout_seconds)
                    )
            except FuturesTimeoutError as exc:
                raise ExtractionError(
                    message=f"LlamaParse timed out after {self._config.timeout_seconds}s",
                    filename=filename,
                    error_type="timeout",
                    details={
                        "timeout_seconds": self._config.timeout_seconds,
                        "tier": 3,
                    },
                    status_code=408,
                ) from exc
            except Exception as exc:
                raise ExtractionError(
                    message=f"LlamaParse failed: {str(exc)[:160]}",
                    filename=filename,
                    error_type="llamaparse_failed",
                    status_code=500,
                ) from exc

        raw_text = self._documents_to_text(documents)
        normalized = TextNormalizer.normalize(raw_text or "")
        is_empty = not normalized.strip()

        page = ExtractedPage(
            page_number=1,
            raw_text=raw_text or "",
            normalized_text=normalized,
            is_empty=is_empty,
            word_count=len(normalized.split()) if normalized else 0,
            char_count=len(normalized),
            line_count=len([ln for ln in normalized.splitlines() if ln.strip()]),
            language=None,
            section_title=None,
            confidence_score=0.9 if not is_empty else 0.0,
        )

        sample_text = page.normalized_text
        doc_language = language or LanguageDetector.detect(sample_text)
        page.language = doc_language

        duration_ms = (time.time() - start_time) * 1000.0

        self._logger.info(
            "pdf_llamaparse_extraction_completed",
            extra={
                "context": {
                    "filename": filename,
                    "document_id": str(document_id),
                    "duration_ms": round(duration_ms, 2),
                }
            },
        )

        return ExtractedDocument(
            document_id=document_id,
            filename=filename,
            format="pdf",
            language=doc_language,
            total_pages=1,
            pages=[page],
            extraction_metadata={
                "extraction_method": "llamaparse",
                "tier": 3,
                "max_pages": self._config.max_pages,
            },
            extraction_duration_ms=duration_ms,
        )
