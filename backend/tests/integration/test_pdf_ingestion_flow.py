"""Integration tests for end-to-end PDF ingestion flow (Story 023).

Tests the complete pipeline: upload → extract → chunk → (embed) → store
"""

from importlib.util import find_spec
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.api.schemas import DocumentMetadata, IngestionConfig
from backend.core.ingestion_models import IngestionStatus
from backend.core.ingestion_orchestrator import IngestionOrchestrator
from backend.core.ingestion_store import IngestionJobStore


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
SINGLE_PAGE_PDF = FIXTURES_DIR / "sample_single_page.pdf"
MULTI_PAGE_PDF = FIXTURES_DIR / "sample_multi_page.pdf"
TABLES_PDF = FIXTURES_DIR / "sample_with_tables.pdf"
LARGE_TEXT_PDF = FIXTURES_DIR / "sample_large_text.pdf"


def _require_pdfplumber() -> None:
    """Skip test if pdfplumber is not installed."""
    if find_spec("pdfplumber") is None:
        pytest.skip("pdfplumber not installed; skipping PDF ingestion tests")


def _require_pdf_fixture(path: Path) -> None:
    """Skip test if pdfplumber or the given PDF fixture is missing."""
    _require_pdfplumber()
    if not path.exists():
        pytest.skip(f"PDF fixture not found: {path}")


def _require_ocr_stack() -> None:
    if find_spec("pypdfium2") is None:
        pytest.skip("pypdfium2 not installed; skipping OCR integration test")
    if find_spec("pytesseract") is None:
        pytest.skip("pytesseract not installed; skipping OCR integration test")

    import pytesseract

    try:
        _ = pytesseract.get_tesseract_version()
    except Exception:
        pytest.skip("tesseract binary not available; skipping OCR integration test")


def _make_scanned_pdf_bytes(*, text: str = "Hello OCR") -> bytes:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        pytest.skip("Pillow is required for OCR integration test")

    try:
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab is required for OCR integration test")

    img = Image.new("RGB", (900, 250), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.multiline_text((40, 60), f"{text}\n{text}", fill=(0, 0, 0))

    img_buf = BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)

    pdf_buf = BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=(612, 792))
    c.drawImage(ImageReader(img_buf), 50, 500, width=500, height=140)
    c.showPage()
    c.save()
    return pdf_buf.getvalue()


class TestPDFIngestionOrchestrator:
    """Tests for PDF ingestion through the orchestrator."""

    @pytest.mark.asyncio
    async def test_single_page_pdf_ingestion(self) -> None:
        """Single-page PDF should ingest successfully."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)

        job_store = IngestionJobStore()
        orchestrator = IngestionOrchestrator(job_store=job_store)

        # Create job
        ingestion_id = uuid4()
        document_id = uuid4()
        job_store.create_job(
            ingestion_id=ingestion_id,
            document_id=document_id,
            files=[],
        )

        # Run ingestion
        content = SINGLE_PAGE_PDF.read_bytes()
        files = [(SINGLE_PAGE_PDF.name, content)]

        result = await orchestrator.ingest_and_store(
            job_id=ingestion_id,
            files=files,
            document_metadata=DocumentMetadata(),
            ingestion_config=IngestionConfig(),
        )

        # Verify extraction succeeded
        assert result.extracted_document is not None
        assert result.extracted_document.total_pages == 1
        assert result.extracted_document.format == "pdf"

        # Verify chunking succeeded
        assert len(result.chunks) > 0

        # Verify job status
        final_job = job_store.get_job(ingestion_id)
        assert final_job is not None
        assert final_job.status == IngestionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_multi_page_pdf_ingestion(self) -> None:
        """Multi-page PDF should extract all pages and create chunks."""
        _require_pdf_fixture(MULTI_PAGE_PDF)

        job_store = IngestionJobStore()
        orchestrator = IngestionOrchestrator(job_store=job_store)

        ingestion_id = uuid4()
        document_id = uuid4()
        job_store.create_job(
            ingestion_id=ingestion_id,
            document_id=document_id,
            files=[],
        )

        content = MULTI_PAGE_PDF.read_bytes()
        files = [(MULTI_PAGE_PDF.name, content)]

        result = await orchestrator.ingest_and_store(
            job_id=ingestion_id,
            files=files,
            document_metadata=DocumentMetadata(),
            ingestion_config=IngestionConfig(),
        )

        assert result.extracted_document is not None
        assert result.extracted_document.total_pages > 1
        assert len(result.chunks) > 0

        # Each page should contribute to chunks
        # (exact count depends on chunking config)

    @pytest.mark.asyncio
    async def test_pdf_with_tables_ingestion(self) -> None:
        """PDF with tables should extract and include table metadata."""
        _require_pdf_fixture(TABLES_PDF)

        job_store = IngestionJobStore()
        orchestrator = IngestionOrchestrator(job_store=job_store)

        ingestion_id = uuid4()
        document_id = uuid4()
        job_store.create_job(
            ingestion_id=ingestion_id,
            document_id=document_id,
            files=[],
        )

        content = TABLES_PDF.read_bytes()
        files = [(TABLES_PDF.name, content)]

        result = await orchestrator.ingest_and_store(
            job_id=ingestion_id,
            files=files,
            document_metadata=DocumentMetadata(),
            ingestion_config=IngestionConfig(),
        )

        assert result.extracted_document is not None
        # Verify table detection metadata
        meta = result.extracted_document.extraction_metadata
        assert "table_pages" in meta
        assert meta["table_pages"] > 0

    @pytest.mark.asyncio
    async def test_large_text_pdf_chunking(self) -> None:
        """Large text PDF should produce multiple chunks."""
        _require_pdf_fixture(LARGE_TEXT_PDF)

        job_store = IngestionJobStore()
        orchestrator = IngestionOrchestrator(job_store=job_store)

        ingestion_id = uuid4()
        document_id = uuid4()
        job_store.create_job(
            ingestion_id=ingestion_id,
            document_id=document_id,
            files=[],
        )

        content = LARGE_TEXT_PDF.read_bytes()
        files = [(LARGE_TEXT_PDF.name, content)]

        result = await orchestrator.ingest_and_store(
            job_id=ingestion_id,
            files=files,
            document_metadata=DocumentMetadata(),
            ingestion_config=IngestionConfig(
                chunk_size_tokens=256,  # Smaller chunks for more granularity
                chunk_overlap_tokens=50,
            ),
        )

        assert result.extracted_document is not None
        # Large text should produce multiple chunks
        assert len(result.chunks) >= 2

    @pytest.mark.asyncio
    async def test_pdf_extraction_metadata_preserved(self) -> None:
        """Extraction metadata should be preserved through pipeline."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)

        job_store = IngestionJobStore()
        orchestrator = IngestionOrchestrator(job_store=job_store)

        ingestion_id = uuid4()
        document_id = uuid4()
        job_store.create_job(
            ingestion_id=ingestion_id,
            document_id=document_id,
            files=[],
        )

        content = SINGLE_PAGE_PDF.read_bytes()
        files = [(SINGLE_PAGE_PDF.name, content)]

        result = await orchestrator.ingest_and_store(
            job_id=ingestion_id,
            files=files,
            document_metadata=DocumentMetadata(),
            ingestion_config=IngestionConfig(),
        )

        meta = result.extracted_document.extraction_metadata
        # Verify new metadata fields from Story 023
        assert "extraction_method" in meta
        assert meta["extraction_method"] == "pdfplumber"
        assert "extractability_ratio" in meta
        assert "is_likely_scanned" in meta

    @pytest.mark.asyncio
    async def test_scanned_pdf_routes_to_ocr_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When Tier 4 is enabled, scanned PDFs should be OCRed end-to-end."""
        _require_pdfplumber()
        _require_ocr_stack()

        # Enable OCR tier via env before constructing orchestrator/services.
        monkeypatch.setenv("PDF_TIER4_ENABLED", "1")
        monkeypatch.setenv("PDF_TIER2_ENABLED", "0")
        monkeypatch.setenv("PDF_TIER3_ENABLED", "0")
        monkeypatch.setenv("PDF_AUTO_FALLBACK", "1")
        monkeypatch.setenv("PDF_TIER4_DPI", "200")
        monkeypatch.setenv("PDF_TIER4_TIMEOUT_SECONDS", "60")

        job_store = IngestionJobStore()
        orchestrator = IngestionOrchestrator(job_store=job_store)

        ingestion_id = uuid4()
        document_id = uuid4()
        job_store.create_job(
            ingestion_id=ingestion_id,
            document_id=document_id,
            files=[],
        )

        ocr_text = "Hello OCR extraction should create chunks"
        content = _make_scanned_pdf_bytes(text=ocr_text)
        files = [("scanned.pdf", content)]

        result = await orchestrator.ingest_and_store(
            job_id=ingestion_id,
            files=files,
            document_metadata=DocumentMetadata(),
            ingestion_config=IngestionConfig(),
        )

        assert result.extracted_document is not None
        meta = result.extracted_document.extraction_metadata
        assert meta.get("extraction_method") == "tesseract_ocr"
        assert any(p.normalized_text.strip() for p in result.extracted_document.pages)
        assert len(result.chunks) > 0


class TestPDFIngestionWithEmbedding:
    """Tests for PDF ingestion with embedding service."""

    @pytest.mark.asyncio
    async def test_pdf_ingestion_with_mock_embedding(self) -> None:
        """PDF ingestion should work with embedding service."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)

        job_store = IngestionJobStore()

        # Mock embedding service
        mock_embedding_service = MagicMock()
        mock_embed_result = MagicMock()
        mock_embed_result.embeddings = [[0.1] * 1536]  # Fake embedding
        mock_embed_result.embedding_duration_ms = 100.0
        mock_embed_result.quality_metrics = {"avg_similarity": 0.95}
        mock_embedding_service.embed_and_store = AsyncMock(
            return_value=mock_embed_result
        )

        orchestrator = IngestionOrchestrator(
            job_store=job_store,
            embedding_service=mock_embedding_service,
        )

        ingestion_id = uuid4()
        document_id = uuid4()
        job_store.create_job(
            ingestion_id=ingestion_id,
            document_id=document_id,
            files=[],
        )

        content = SINGLE_PAGE_PDF.read_bytes()
        files = [(SINGLE_PAGE_PDF.name, content)]

        await orchestrator.ingest_and_store(
            job_id=ingestion_id,
            files=files,
            document_metadata=DocumentMetadata(),
            ingestion_config=IngestionConfig(),
        )

        # Verify embedding was called
        mock_embedding_service.embed_and_store.assert_called_once()

        # Verify job completed
        final_job = job_store.get_job(ingestion_id)
        assert final_job.status == IngestionStatus.COMPLETED


class TestPDFIngestionErrors:
    """Tests for error handling in PDF ingestion."""

    @pytest.mark.asyncio
    async def test_corrupt_pdf_fails_gracefully(self) -> None:
        """Corrupt PDF should fail with proper error status."""
        _require_pdfplumber()

        job_store = IngestionJobStore()
        orchestrator = IngestionOrchestrator(job_store=job_store)

        ingestion_id = uuid4()
        document_id = uuid4()
        job_store.create_job(
            ingestion_id=ingestion_id,
            document_id=document_id,
            files=[],
        )

        # Corrupt PDF content
        files = [("corrupt.pdf", b"not a valid pdf file")]

        await orchestrator.ingest_and_store(
            job_id=ingestion_id,
            files=files,
            document_metadata=DocumentMetadata(),
            ingestion_config=IngestionConfig(),
        )

        # Job should be marked as failed
        final_job = job_store.get_job(ingestion_id)
        assert final_job.status == IngestionStatus.FAILED
        assert final_job.error_message is not None
        assert "extraction" in (final_job.error_stage or "").lower()

    @pytest.mark.asyncio
    async def test_empty_files_fails(self) -> None:
        """Empty files list should fail."""
        _require_pdfplumber()

        job_store = IngestionJobStore()
        orchestrator = IngestionOrchestrator(job_store=job_store)

        ingestion_id = uuid4()
        document_id = uuid4()
        job_store.create_job(
            ingestion_id=ingestion_id,
            document_id=document_id,
            files=[],
        )

        # Empty files list
        files = []

        await orchestrator.ingest_and_store(
            job_id=ingestion_id,
            files=files,
            document_metadata=DocumentMetadata(),
            ingestion_config=IngestionConfig(),
        )

        final_job = job_store.get_job(ingestion_id)
        assert final_job.status == IngestionStatus.FAILED
