"""Tests for PDF extraction pipeline (Story 023).

Tests cover:
- Tier selection based on PDF analysis
- Tier 1 (pdfplumber) extraction via pipeline
- Fallback behavior when tiers fail
- Pipeline configuration options
- Available tiers reporting
"""

from importlib.util import find_spec
from io import BytesIO
import os
from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.data_models import ExtractedDocument, ExtractedPage
from backend.core.extractors.pdf_pipeline import (
    PDFExtractionPipeline,
    PDFPipelineConfig,
    PipelineResult,
)


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
SINGLE_PAGE_PDF = FIXTURES_DIR / "sample_single_page.pdf"
MULTI_PAGE_PDF = FIXTURES_DIR / "sample_multi_page.pdf"
TABLES_PDF = FIXTURES_DIR / "sample_with_tables.pdf"


def _require_pdfplumber() -> None:
    """Skip test if pdfplumber is not installed."""
    if find_spec("pdfplumber") is None:
        pytest.skip("pdfplumber not installed; skipping PDF pipeline tests")


def _require_pdf_fixture(path: Path) -> None:
    """Skip test if pdfplumber or the given PDF fixture is missing."""
    _require_pdfplumber()
    if not path.exists():
        pytest.skip(f"PDF fixture not found: {path}")


def _require_ocr_stack() -> None:
    if find_spec("pypdfium2") is None:
        pytest.skip("pypdfium2 not installed; skipping OCR tests")
    if find_spec("pytesseract") is None:
        pytest.skip("pytesseract not installed; skipping OCR tests")

    import pytesseract

    try:
        _ = pytesseract.get_tesseract_version()
    except Exception:
        pytest.skip("tesseract binary not available; skipping OCR tests")


def _make_scanned_pdf_bytes(*, text: str = "Hello OCR") -> bytes:
    """Create a PDF that contains only an embedded image with text."""

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        pytest.skip("Pillow is required for OCR tests")

    try:
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab is required for OCR tests")

    img = Image.new("RGB", (900, 250), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 80), text, fill=(0, 0, 0))

    img_buf = BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)

    pdf_buf = BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=(612, 792))
    c.drawImage(ImageReader(img_buf), 50, 500, width=500, height=140)
    c.showPage()
    c.save()
    return pdf_buf.getvalue()


class TestPipelineTier1:
    """Tests for Tier 1 (pdfplumber) extraction via pipeline."""

    def test_extracts_simple_pdf(self) -> None:
        """Pipeline extracts simple PDF using Tier 1."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)
        content = SINGLE_PAGE_PDF.read_bytes()

        pipeline = PDFExtractionPipeline()
        result = pipeline.extract(
            content=content,
            document_id=uuid4(),
            filename=SINGLE_PAGE_PDF.name,
        )

        assert isinstance(result, PipelineResult)
        assert result.tier_used == 1
        assert result.tier_name == "pdfplumber"
        assert result.document.total_pages == 1
        assert result.fallback_attempted is False

    def test_extracts_multi_page_pdf(self) -> None:
        """Pipeline extracts multi-page PDF correctly."""
        _require_pdf_fixture(MULTI_PAGE_PDF)
        content = MULTI_PAGE_PDF.read_bytes()

        pipeline = PDFExtractionPipeline()
        result = pipeline.extract(
            content=content,
            document_id=uuid4(),
            filename=MULTI_PAGE_PDF.name,
        )

        assert result.document.total_pages > 1
        assert result.tier_used == 1

    def test_includes_analysis_in_result(self) -> None:
        """Pipeline result includes PDF analysis."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)
        content = SINGLE_PAGE_PDF.read_bytes()

        pipeline = PDFExtractionPipeline()
        result = pipeline.extract(
            content=content,
            document_id=uuid4(),
            filename=SINGLE_PAGE_PDF.name,
        )

        assert result.analysis is not None
        assert result.analysis.page_count == 1
        assert result.analysis.has_text is True

    def test_tracks_pipeline_duration(self) -> None:
        """Pipeline result includes total pipeline duration."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)
        content = SINGLE_PAGE_PDF.read_bytes()

        pipeline = PDFExtractionPipeline()
        result = pipeline.extract(
            content=content,
            document_id=uuid4(),
            filename=SINGLE_PAGE_PDF.name,
        )

        assert result.pipeline_duration_ms > 0


class TestTierSelection:
    """Tests for tier selection logic."""

    def test_selects_tier1_for_searchable_pdf(self) -> None:
        """Searchable PDF should use Tier 1."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)
        content = SINGLE_PAGE_PDF.read_bytes()

        pipeline = PDFExtractionPipeline()
        result = pipeline.extract(
            content=content,
            document_id=uuid4(),
            filename=SINGLE_PAGE_PDF.name,
        )

        # Searchable PDF should use tier 1 or 2 (depending on analysis)
        assert result.tier_used in [1, 2]

    def test_force_tier_overrides_analysis(self) -> None:
        """force_tier parameter should override automatic selection."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)
        content = SINGLE_PAGE_PDF.read_bytes()

        pipeline = PDFExtractionPipeline()
        result = pipeline.extract(
            content=content,
            document_id=uuid4(),
            filename=SINGLE_PAGE_PDF.name,
            force_tier=1,
        )

        assert result.tier_used == 1


class TestFallbackBehavior:
    """Tests for fallback behavior when tiers fail."""

    def test_fallback_disabled_raises_on_failure(self) -> None:
        """With auto_fallback=False, failure should raise immediately."""
        _require_pdfplumber()
        from backend.core.exceptions import ExtractionError

        config = PDFPipelineConfig(
            auto_fallback=False,
            tier1_enabled=True,
        )
        pipeline = PDFExtractionPipeline(config)

        # Corrupt content should fail
        with pytest.raises(ExtractionError):
            pipeline.extract(
                content=b"not a valid pdf",
                document_id=uuid4(),
                filename="corrupt.pdf",
            )

    def test_all_tiers_failed_error(self) -> None:
        """When all tiers fail, should raise comprehensive error."""
        _require_pdfplumber()
        from backend.core.exceptions import ExtractionError

        # Only tier 1 enabled, and it will fail on corrupt content
        config = PDFPipelineConfig(
            auto_fallback=True,
            tier1_enabled=True,
            tier2_enabled=False,
            tier3_enabled=False,
            tier4_enabled=False,
        )
        pipeline = PDFExtractionPipeline(config)

        with pytest.raises(ExtractionError) as exc_info:
            pipeline.extract(
                content=b"not a valid pdf",
                document_id=uuid4(),
                filename="corrupt.pdf",
            )

        assert "all_tiers_failed" in str(exc_info.value.details.get("error_type", ""))


class TestPipelineConfiguration:
    """Tests for pipeline configuration options."""

    def test_default_config(self) -> None:
        """Default config should have tier 1 enabled."""
        config = PDFPipelineConfig()
        assert config.tier1_enabled is True
        assert config.tier2_enabled is False
        assert config.tier3_enabled is False
        assert config.tier4_enabled is False

    def test_custom_config(self) -> None:
        """Custom config should be respected."""
        config = PDFPipelineConfig(
            tier1_enabled=True,
            tier4_enabled=True,
            extractability_threshold=0.7,
        )
        pipeline = PDFExtractionPipeline(config)

        tiers = pipeline.get_available_tiers()
        assert tiers[1]["enabled"] is True
        assert tiers[4]["enabled"] is True

    def test_get_available_tiers(self) -> None:
        """get_available_tiers should return tier information."""
        pipeline = PDFExtractionPipeline()
        tiers = pipeline.get_available_tiers()

        assert 1 in tiers
        assert 2 in tiers
        assert 3 in tiers
        assert 4 in tiers

        # Tier 1 should be implemented
        assert tiers[1]["implemented"] is True
        assert tiers[1]["name"] == "pdfplumber"

        # Tier 2/3/4 are implemented.
        assert tiers[2]["implemented"] is True
        assert tiers[3]["implemented"] is True
        assert tiers[4]["implemented"] is True


class TestTier2DoclingMocked:
    def test_docling_tier_uses_extractor_without_importing_docling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _fake_extract_document(
            self,
            *,
            content: bytes,
            document_id,
            filename: str,
            language=None,
            password=None,
        ):
            _ = (self, content, language, password)
            return ExtractedDocument(
                document_id=document_id,
                filename=filename,
                format="pdf",
                language="en",
                total_pages=1,
                pages=[
                    ExtractedPage(
                        page_number=1,
                        raw_text="Hello from Docling",
                        normalized_text="Hello from Docling",
                        is_empty=False,
                        word_count=3,
                        char_count=len("Hello from Docling"),
                        line_count=1,
                        language="en",
                        section_title=None,
                        confidence_score=0.85,
                    )
                ],
                extraction_metadata={"extraction_method": "docling"},
                extraction_duration_ms=1.0,
            )

        from backend.core.extractors import pdf_docling_extractor

        monkeypatch.setattr(
            pdf_docling_extractor.PDFDoclingExtractor,
            "extract_document",
            _fake_extract_document,
            raising=True,
        )

        config = PDFPipelineConfig(
            tier1_enabled=False,
            tier2_enabled=True,
            auto_fallback=False,
        )
        pipeline = PDFExtractionPipeline(config)

        result = pipeline.extract(
            content=b"%PDF-pretend-bytes%",
            document_id=uuid4(),
            filename="complex.pdf",
            force_tier=2,
        )

        assert result.tier_used == 2
        assert result.tier_name == "docling"
        assert (
            "docling"
            in (
                result.document.extraction_metadata.get("extraction_method") or ""
            ).lower()
        )
        assert "hello" in result.document.pages[0].normalized_text.lower()


class TestTier3LlamaParseMocked:
    def test_llamaparse_tier_uses_extractor_without_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _fake_extract_document(
            self,
            *,
            content: bytes,
            document_id,
            filename: str,
            language=None,
            password=None,
        ):
            _ = (self, content, language, password)
            return ExtractedDocument(
                document_id=document_id,
                filename=filename,
                format="pdf",
                language="en",
                total_pages=1,
                pages=[
                    ExtractedPage(
                        page_number=1,
                        raw_text="Hello from LlamaParse",
                        normalized_text="Hello from LlamaParse",
                        is_empty=False,
                        word_count=3,
                        char_count=len("Hello from LlamaParse"),
                        line_count=1,
                        language="en",
                        section_title=None,
                        confidence_score=0.9,
                    )
                ],
                extraction_metadata={"extraction_method": "llamaparse"},
                extraction_duration_ms=1.0,
            )

        from backend.core.extractors import pdf_llamaparse_extractor

        monkeypatch.setattr(
            pdf_llamaparse_extractor.PDFLlamaParseExtractor,
            "extract_document",
            _fake_extract_document,
            raising=True,
        )

        config = PDFPipelineConfig(
            tier1_enabled=False,
            tier3_enabled=True,
            auto_fallback=False,
        )
        pipeline = PDFExtractionPipeline(config)

        result = pipeline.extract(
            content=b"%PDF-pretend-bytes%",
            document_id=uuid4(),
            filename="premium.pdf",
            force_tier=3,
        )

        assert result.tier_used == 3
        assert result.tier_name == "llamaparse"
        assert (
            "llamaparse"
            in (
                result.document.extraction_metadata.get("extraction_method") or ""
            ).lower()
        )
        assert "hello" in result.document.pages[0].normalized_text.lower()


class TestTier3LlamaParseSmoke:
    def test_llamaparse_smoke_when_key_set(self) -> None:
        api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if not api_key:
            pytest.skip("LLAMA_CLOUD_API_KEY not set; skipping LlamaParse smoke")

        if not SINGLE_PAGE_PDF.exists():
            pytest.skip(f"PDF fixture not found: {SINGLE_PAGE_PDF}")

        content = SINGLE_PAGE_PDF.read_bytes()
        config = PDFPipelineConfig(
            tier1_enabled=False,
            tier3_enabled=True,
            auto_fallback=False,
        )
        pipeline = PDFExtractionPipeline(config)
        result = pipeline.extract(
            content=content,
            document_id=uuid4(),
            filename=SINGLE_PAGE_PDF.name,
            force_tier=3,
        )

        assert result.tier_used == 3
        assert result.document.total_pages >= 1
        assert any(p.normalized_text.strip() for p in result.document.pages)


class TestTier4OCR:
    def test_ocr_extracts_text_from_scanned_pdf(self) -> None:
        _require_ocr_stack()

        content = _make_scanned_pdf_bytes(text="Hello OCR")

        config = PDFPipelineConfig(
            tier1_enabled=False,
            tier4_enabled=True,
            auto_fallback=False,
            tier4_timeout_seconds=60,
            tier4_dpi=200,
            tier4_lang="en",
        )
        pipeline = PDFExtractionPipeline(config)
        result = pipeline.extract(
            content=content,
            document_id=uuid4(),
            filename="scanned.pdf",
            force_tier=4,
        )

        assert result.tier_used == 4
        assert result.tier_name == "tesseract_ocr"
        assert result.document.total_pages == 1
        assert "hello" in result.document.pages[0].normalized_text.lower()

    def test_ocr_invalid_tesseract_cmd_raises(self) -> None:
        if find_spec("pypdfium2") is None or find_spec("pytesseract") is None:
            pytest.skip("OCR deps not installed; skipping")

        from backend.core.exceptions import ExtractionError
        from backend.core.extractors.pdf_ocr_extractor import (
            PDFOCRConfig,
            PDFOCRExtractor,
        )

        content = _make_scanned_pdf_bytes(text="Hello OCR")
        extractor = PDFOCRExtractor(
            PDFOCRConfig(
                dpi=150,
                lang="eng",
                timeout_seconds=60,
                tesseract_cmd=r"C:\\does-not-exist\\tesseract.exe",
            )
        )

        with pytest.raises(ExtractionError) as exc_info:
            extractor.extract_document(
                content=content,
                document_id=uuid4(),
                filename="scanned.pdf",
            )

        assert exc_info.value.details["error_type"] == "dependency_not_available"


class TestErrorHandling:
    """Tests for error handling in pipeline."""

    def test_corrupt_pdf_error(self) -> None:
        """Corrupt PDF should raise ExtractionError."""
        _require_pdfplumber()
        from backend.core.exceptions import ExtractionError

        pipeline = PDFExtractionPipeline()

        with pytest.raises(ExtractionError):
            pipeline.extract(
                content=b"not a valid pdf",
                document_id=uuid4(),
                filename="corrupt.pdf",
            )

    def test_empty_content_error(self) -> None:
        """Empty content should raise ExtractionError."""
        _require_pdfplumber()
        from backend.core.exceptions import ExtractionError

        pipeline = PDFExtractionPipeline()

        with pytest.raises(ExtractionError):
            pipeline.extract(
                content=b"",
                document_id=uuid4(),
                filename="empty.pdf",
            )
