"""PDF Extraction Pipeline with tiered routing (Story 023).

Implements intelligent tier-based PDF extraction:
- Tier 1 (Fast): pdfplumber for searchable native PDFs
- Tier 2 (Smart): Reserved for Docling (complex layouts) - not implemented
- Tier 3 (AI): Reserved for LlamaParse (premium) - not implemented
- Tier 4 (Fallback): Reserved for OCR (scanned PDFs) - not implemented

The pipeline analyzes PDF characteristics and routes to the appropriate
extractor, with automatic fallback on failure.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from backend.core.data_models import ExtractedDocument
from backend.core.exceptions import ExtractionError
from backend.core.extractors.pdf_extractor import (
    PDFAnalysisResult,
    PDFExtractionConfig,
    PDFExtractor,
)
from backend.core.extractors.pdf_docling_extractor import (
    PDFDoclingConfig,
    PDFDoclingExtractor,
)
from backend.core.extractors.pdf_llamaparse_extractor import (
    PDFLlamaParseConfig,
    PDFLlamaParseExtractor,
)
from backend.core.extractors.pdf_ocr_extractor import PDFOCRConfig, PDFOCRExtractor
from backend.core.logging import get_logger


@dataclass
class PDFPipelineConfig:
    """Configuration for the PDF extraction pipeline."""

    # Tier 1 (pdfplumber) - always enabled
    tier1_enabled: bool = True
    tier1_config: PDFExtractionConfig = field(default_factory=PDFExtractionConfig)

    # Tier 2 (Docling) - optional, requires docling package
    tier2_enabled: bool = False
    tier2_timeout_seconds: int = 60

    # Tier 3 (LlamaParse) - optional, requires API key
    tier3_enabled: bool = False
    tier3_api_key: Optional[str] = None
    tier3_timeout_seconds: int = 120

    # Tier 4 (OCR) - optional, requires paddleocr or tesseract
    tier4_enabled: bool = False
    tier4_timeout_seconds: int = 120
    tier4_dpi: int = 300
    tier4_lang: str = "en"

    # Pipeline behavior
    auto_fallback: bool = True
    extractability_threshold: float = 0.5
    log_tier_decisions: bool = True

    @classmethod
    def from_env(cls) -> "PDFPipelineConfig":
        def _parse_bool(value: Optional[str], default: bool) -> bool:
            if value is None:
                return default
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}

        def _parse_int(value: Optional[str], default: int) -> int:
            if value is None:
                return default
            try:
                return int(value)
            except ValueError:
                return default

        def _parse_float(value: Optional[str], default: float) -> float:
            if value is None:
                return default
            try:
                return float(value)
            except ValueError:
                return default

        base = cls()

        return cls(
            tier1_enabled=_parse_bool(
                os.getenv("PDF_TIER1_ENABLED"), base.tier1_enabled
            ),
            tier1_config=base.tier1_config,
            tier2_enabled=_parse_bool(
                os.getenv("PDF_TIER2_ENABLED"), base.tier2_enabled
            ),
            tier2_timeout_seconds=_parse_int(
                os.getenv("PDF_TIER2_TIMEOUT_SECONDS"), base.tier2_timeout_seconds
            ),
            tier3_enabled=_parse_bool(
                os.getenv("PDF_TIER3_ENABLED"), base.tier3_enabled
            ),
            tier3_api_key=os.getenv("LLAMA_CLOUD_API_KEY") or base.tier3_api_key,
            tier3_timeout_seconds=_parse_int(
                os.getenv("PDF_TIER3_TIMEOUT_SECONDS"), base.tier3_timeout_seconds
            ),
            tier4_enabled=_parse_bool(
                os.getenv("PDF_TIER4_ENABLED"), base.tier4_enabled
            ),
            tier4_timeout_seconds=_parse_int(
                os.getenv("PDF_TIER4_TIMEOUT_SECONDS"), base.tier4_timeout_seconds
            ),
            tier4_dpi=_parse_int(os.getenv("PDF_TIER4_DPI"), base.tier4_dpi),
            tier4_lang=os.getenv("PDF_TIER4_LANG") or base.tier4_lang,
            auto_fallback=_parse_bool(
                os.getenv("PDF_AUTO_FALLBACK"), base.auto_fallback
            ),
            extractability_threshold=_parse_float(
                os.getenv("PDF_EXTRACTABILITY_THRESHOLD"), base.extractability_threshold
            ),
            log_tier_decisions=_parse_bool(
                os.getenv("PDF_LOG_TIER_DECISIONS"), base.log_tier_decisions
            ),
        )


@dataclass
class PipelineResult:
    """Result from the PDF extraction pipeline."""

    document: ExtractedDocument
    tier_used: int
    tier_name: str
    fallback_attempted: bool = False
    fallback_reason: Optional[str] = None
    analysis: Optional[PDFAnalysisResult] = None
    pipeline_duration_ms: float = 0.0


class PDFExtractionPipeline:
    """Tier-based PDF extraction with intelligent routing and fallback.

    Routes PDFs to the appropriate extraction tier based on document
    characteristics (extractability, tables, scanned content).

    Currently implements:
    - Tier 1: pdfplumber (production-ready)

    Future tiers (stubs):
    - Tier 2: Docling for complex layouts
    - Tier 3: LlamaParse for premium AI extraction
    - Tier 4: OCR for scanned documents
    """

    def __init__(self, config: Optional[PDFPipelineConfig] = None) -> None:
        self._config = config or PDFPipelineConfig.from_env()
        self._logger = get_logger("rag.core.pdf_pipeline")

        # Initialize Tier 1 extractor
        self._tier1_extractor = PDFExtractor(self._config.tier1_config)

    def extract(
        self,
        content: bytes,
        document_id: UUID,
        filename: str,
        language: Optional[str] = None,
        password: Optional[str] = None,
        force_tier: Optional[int] = None,
    ) -> PipelineResult:
        """Extract PDF using intelligent tier-based routing.

        Args:
            content: Raw PDF bytes
            document_id: UUID for the document
            filename: Original filename
            language: Optional language hint
            password: Optional password for encrypted PDFs
            force_tier: Force a specific tier (1-4), bypassing analysis

        Returns:
            PipelineResult with extracted document and tier metadata
        """
        start_time = time.time()

        # Analyze PDF to determine best tier
        analysis = PDFExtractor.analyze_pdf(content, filename)

        # Determine which tier to use
        if force_tier is not None:
            target_tier = force_tier
            self._logger.info(
                "pdf_pipeline_forced_tier",
                extra={
                    "context": {
                        "filename": filename,
                        "forced_tier": target_tier,
                    }
                },
            )
        else:
            target_tier = self._select_tier(analysis, filename)

        # Execute extraction with fallback
        result = self._execute_with_fallback(
            content=content,
            document_id=document_id,
            filename=filename,
            language=language,
            password=password,
            target_tier=target_tier,
            analysis=analysis,
        )

        result.pipeline_duration_ms = (time.time() - start_time) * 1000.0
        result.analysis = analysis

        self._logger.info(
            "pdf_pipeline_completed",
            extra={
                "context": {
                    "filename": filename,
                    "document_id": str(document_id),
                    "tier_used": result.tier_used,
                    "tier_name": result.tier_name,
                    "fallback_attempted": result.fallback_attempted,
                    "pipeline_duration_ms": round(result.pipeline_duration_ms, 2),
                    "extraction_duration_ms": round(
                        result.document.extraction_duration_ms, 2
                    ),
                }
            },
        )

        return result

    def _select_tier(self, analysis: PDFAnalysisResult, filename: str) -> int:
        """Select the best extraction tier based on PDF analysis."""
        recommended = analysis.recommended_tier

        # Check if recommended tier is available
        if recommended == 1 and self._config.tier1_enabled:
            tier = 1
        elif recommended == 2 and self._config.tier2_enabled:
            tier = 2
        elif recommended == 3 and self._config.tier3_enabled:
            tier = 3
        elif recommended == 4 and self._config.tier4_enabled:
            tier = 4
        else:
            # Fall back to best available tier
            if self._config.tier1_enabled:
                tier = 1
            elif self._config.tier4_enabled:
                tier = 4
            else:
                tier = 1  # Default to tier 1 even if "disabled"

        if self._config.log_tier_decisions:
            self._logger.info(
                "pdf_pipeline_tier_selected",
                extra={
                    "context": {
                        "filename": filename,
                        "recommended_tier": recommended,
                        "selected_tier": tier,
                        "extractability_ratio": round(analysis.extractability_ratio, 3),
                        "has_tables": analysis.has_tables,
                        "is_scanned": analysis.is_scanned,
                    }
                },
            )

        return tier

    def _execute_with_fallback(
        self,
        content: bytes,
        document_id: UUID,
        filename: str,
        language: Optional[str],
        password: Optional[str],
        target_tier: int,
        analysis: PDFAnalysisResult,
    ) -> PipelineResult:
        """Execute extraction with automatic fallback on failure."""
        fallback_reason: Optional[str] = None

        # Try target tier
        try:
            document, tier_name = self._extract_tier(
                tier=target_tier,
                content=content,
                document_id=document_id,
                filename=filename,
                language=language,
                password=password,
            )
            return PipelineResult(
                document=document,
                tier_used=target_tier,
                tier_name=tier_name,
                fallback_attempted=False,
            )
        except ExtractionError as exc:
            if not self._config.auto_fallback:
                raise

            fallback_reason = str(exc)[:100]
            self._logger.warning(
                "pdf_pipeline_tier_failed",
                extra={
                    "context": {
                        "filename": filename,
                        "failed_tier": target_tier,
                        "error": fallback_reason,
                    }
                },
            )

        # Try fallback tiers in order
        fallback_order = self._get_fallback_order(target_tier)

        for fallback_tier in fallback_order:
            try:
                document, tier_name = self._extract_tier(
                    tier=fallback_tier,
                    content=content,
                    document_id=document_id,
                    filename=filename,
                    language=language,
                    password=password,
                )
                return PipelineResult(
                    document=document,
                    tier_used=fallback_tier,
                    tier_name=tier_name,
                    fallback_attempted=True,
                    fallback_reason=fallback_reason,
                )
            except ExtractionError:
                continue

        # All tiers failed
        raise ExtractionError(
            message=f"All extraction tiers failed for {filename}",
            filename=filename,
            error_type="all_tiers_failed",
            details={
                "attempted_tiers": [target_tier] + fallback_order,
                "original_error": fallback_reason,
            },
            status_code=500,
        )

    def _get_fallback_order(self, failed_tier: int) -> List[int]:
        """Get ordered list of fallback tiers to try."""
        all_tiers = [1, 2, 3, 4]
        available = []

        for tier in all_tiers:
            if tier == failed_tier:
                continue
            if tier == 1 and self._config.tier1_enabled:
                available.append(tier)
            elif tier == 2 and self._config.tier2_enabled:
                available.append(tier)
            elif tier == 3 and self._config.tier3_enabled:
                available.append(tier)
            elif tier == 4 and self._config.tier4_enabled:
                available.append(tier)

        return available

    def _extract_tier(
        self,
        tier: int,
        content: bytes,
        document_id: UUID,
        filename: str,
        language: Optional[str],
        password: Optional[str],
    ) -> Tuple[ExtractedDocument, str]:
        """Execute extraction for a specific tier."""
        if tier == 1:
            return self._extract_tier1(
                content, document_id, filename, language, password
            )
        elif tier == 2:
            return self._extract_tier2(
                content, document_id, filename, language, password
            )
        elif tier == 3:
            return self._extract_tier3(
                content, document_id, filename, language, password
            )
        elif tier == 4:
            return self._extract_tier4(
                content, document_id, filename, language, password
            )
        else:
            raise ValueError(f"Invalid tier: {tier}")

    def _extract_tier1(
        self,
        content: bytes,
        document_id: UUID,
        filename: str,
        language: Optional[str],
        password: Optional[str],
    ) -> Tuple[ExtractedDocument, str]:
        """Tier 1: pdfplumber extraction."""
        document = self._tier1_extractor.extract_document(
            content=content,
            document_id=document_id,
            filename=filename,
            language=language,
            password=password,
        )
        return document, "pdfplumber"

    def _extract_tier2(
        self,
        content: bytes,
        document_id: UUID,
        filename: str,
        language: Optional[str],
        password: Optional[str],
    ) -> Tuple[ExtractedDocument, str]:
        """Tier 2: Docling extraction."""

        docling_config = PDFDoclingConfig(
            timeout_seconds=self._config.tier2_timeout_seconds,
            max_pages=self._config.tier1_config.max_pages,
        )
        extractor = PDFDoclingExtractor(docling_config)
        document = extractor.extract_document(
            content=content,
            document_id=document_id,
            filename=filename,
            language=language,
            password=password,
        )
        return document, "docling"

    def _extract_tier3(
        self,
        content: bytes,
        document_id: UUID,
        filename: str,
        language: Optional[str],
        password: Optional[str],
    ) -> Tuple[ExtractedDocument, str]:
        """Tier 3: LlamaParse extraction."""

        llamaparse_config = PDFLlamaParseConfig(
            api_key=self._config.tier3_api_key,
            timeout_seconds=self._config.tier3_timeout_seconds,
            max_pages=self._config.tier1_config.max_pages,
        )
        extractor = PDFLlamaParseExtractor(llamaparse_config)
        document = extractor.extract_document(
            content=content,
            document_id=document_id,
            filename=filename,
            language=language,
            password=password,
        )
        return document, "llamaparse"

    def _extract_tier4(
        self,
        content: bytes,
        document_id: UUID,
        filename: str,
        language: Optional[str],
        password: Optional[str],
    ) -> Tuple[ExtractedDocument, str]:
        """Tier 4: OCR extraction."""

        def _normalize_ocr_lang(lang: str) -> str:
            if lang.strip().lower() == "en":
                return "eng"
            return lang

        ocr_config = PDFOCRConfig(
            dpi=self._config.tier4_dpi,
            lang=_normalize_ocr_lang(self._config.tier4_lang),
            timeout_seconds=self._config.tier4_timeout_seconds,
            max_pages=self._config.tier1_config.max_pages,
        )
        extractor = PDFOCRExtractor(ocr_config)
        document = extractor.extract_document(
            content=content,
            document_id=document_id,
            filename=filename,
            language=language,
            password=password,
        )
        return document, "tesseract_ocr"

    def get_available_tiers(self) -> Dict[int, Dict[str, Any]]:
        """Return information about available extraction tiers."""
        return {
            1: {
                "name": "pdfplumber",
                "enabled": self._config.tier1_enabled,
                "implemented": True,
                "description": "Fast extraction for searchable PDFs",
            },
            2: {
                "name": "docling",
                "enabled": self._config.tier2_enabled,
                "implemented": True,
                "description": "Smart extraction for complex layouts",
            },
            3: {
                "name": "llamaparse",
                "enabled": self._config.tier3_enabled,
                "implemented": True,
                "description": "AI-powered extraction for premium documents",
            },
            4: {
                "name": "ocr",
                "enabled": self._config.tier4_enabled,
                "implemented": True,
                "description": "OCR fallback for scanned documents",
            },
        }
