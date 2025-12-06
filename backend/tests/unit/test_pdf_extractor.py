from importlib.util import find_spec
from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.extractors.pdf_extractor import PDFExtractor


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
SINGLE_PAGE_PDF = FIXTURES_DIR / "sample_single_page.pdf"
MULTI_PAGE_PDF = FIXTURES_DIR / "sample_multi_page.pdf"
EMPTY_PAGE_PDF = FIXTURES_DIR / "sample_with_empty_pages.pdf"


def _require_pdf_fixture(path: Path) -> None:
    """Skip test if pdfplumber or the given PDF fixture is missing."""

    if find_spec("pdfplumber") is None:  # type: ignore[arg-type]
        pytest.skip("pdfplumber not installed; skipping PDF extractor tests")

    if not path.exists():
        pytest.skip(f"PDF fixture not found: {path}")


def test_pdf_extractor_single_page_basic() -> None:
    """Single-page PDF extraction produces one non-empty page and metrics."""

    _require_pdf_fixture(SINGLE_PAGE_PDF)
    content = SINGLE_PAGE_PDF.read_bytes()

    result = PDFExtractor.extract(
        content=content,
        document_id=uuid4(),
        filename=SINGLE_PAGE_PDF.name,
    )

    assert result.total_pages == 1
    assert len(result.pages) == 1
    assert any(not page.is_empty for page in result.pages)

    meta = result.extraction_metadata
    assert meta["total_words"] == sum(p.word_count for p in result.pages)
    assert meta["total_chars"] == sum(p.char_count for p in result.pages)
    assert meta["empty_pages"] + meta["non_empty_pages"] == result.total_pages


def test_pdf_extractor_tracks_page_numbers_for_multi_page() -> None:
    """Multi-page PDF has correctly numbered pages in order."""

    _require_pdf_fixture(MULTI_PAGE_PDF)
    content = MULTI_PAGE_PDF.read_bytes()

    result = PDFExtractor.extract(
        content=content,
        document_id=uuid4(),
        filename=MULTI_PAGE_PDF.name,
    )

    assert result.total_pages == len(result.pages)
    assert result.total_pages > 1
    for i, page in enumerate(result.pages):
        assert page.page_number == i


def test_pdf_extractor_marks_empty_pages_and_updates_metrics() -> None:
    """PDFs with near-empty pages should reflect them in metrics."""

    _require_pdf_fixture(EMPTY_PAGE_PDF)
    content = EMPTY_PAGE_PDF.read_bytes()

    result = PDFExtractor.extract(
        content=content,
        document_id=uuid4(),
        filename=EMPTY_PAGE_PDF.name,
    )

    meta = result.extraction_metadata
    # Rely on the fixture to contain at least one empty/near-empty page.
    assert meta["empty_pages"] >= 1
    assert meta["empty_pages"] + meta["non_empty_pages"] == result.total_pages
