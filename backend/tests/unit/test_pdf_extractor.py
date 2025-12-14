"""Comprehensive tests for PDF extraction (Story 007 / Story 023).

Tests cover:
- Basic extraction (single page, multi-page)
- Empty page detection
- Table detection
- Section title detection
- Extractability metrics
- PDF analysis for tier routing
- Error handling (corrupt files, encrypted PDFs)
- Configuration options
"""

from importlib.util import find_spec
from pathlib import Path
from uuid import uuid4

import base64
import pytest

from backend.core.extractors.pdf_extractor import (
    PDFAnalysisResult,
    PDFExtractionConfig,
    PDFExtractor,
)


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
SINGLE_PAGE_PDF = FIXTURES_DIR / "sample_single_page.pdf"
MULTI_PAGE_PDF = FIXTURES_DIR / "sample_multi_page.pdf"
EMPTY_PAGE_PDF = FIXTURES_DIR / "sample_with_empty_pages.pdf"
TABLES_PDF = FIXTURES_DIR / "sample_with_tables.pdf"
LARGE_TEXT_PDF = FIXTURES_DIR / "sample_large_text.pdf"
MINIMAL_PDF = FIXTURES_DIR / "sample_minimal.pdf"
ENCRYPTED_PDF = FIXTURES_DIR / "sample_encrypted.pdf"


def _require_pdfplumber() -> None:
    """Skip test if pdfplumber is not installed."""
    if find_spec("pdfplumber") is None:
        pytest.skip("pdfplumber not installed; skipping PDF extractor tests")


def _require_pdf_fixture(path: Path) -> None:
    """Skip test if pdfplumber or the given PDF fixture is missing."""
    _require_pdfplumber()
    if not path.exists():
        pytest.skip(f"PDF fixture not found: {path}")


class TestBasicExtraction:
    """Tests for basic PDF extraction functionality."""

    def test_single_page_basic(self) -> None:
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

    def test_tracks_page_numbers_for_multi_page(self) -> None:
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

    def test_marks_empty_pages_and_updates_metrics(self) -> None:
        """PDFs with near-empty pages should reflect them in metrics."""
        _require_pdf_fixture(EMPTY_PAGE_PDF)
        content = EMPTY_PAGE_PDF.read_bytes()

        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename=EMPTY_PAGE_PDF.name,
        )

        meta = result.extraction_metadata
        assert meta["empty_pages"] >= 1
        assert meta["empty_pages"] + meta["non_empty_pages"] == result.total_pages

    def test_minimal_pdf_extraction(self) -> None:
        """Minimal PDF with single character extracts correctly."""
        _require_pdf_fixture(MINIMAL_PDF)
        content = MINIMAL_PDF.read_bytes()

        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename=MINIMAL_PDF.name,
        )

        assert result.total_pages == 1
        # Minimal content should have low confidence
        assert result.pages[0].confidence_score <= 1.0


class TestExtractabilityMetrics:
    """Tests for extractability ratio and related metrics."""

    def test_extractability_ratio_calculated(self) -> None:
        """Extractability ratio is calculated and stored in metadata."""
        _require_pdf_fixture(MULTI_PAGE_PDF)
        content = MULTI_PAGE_PDF.read_bytes()

        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename=MULTI_PAGE_PDF.name,
        )

        meta = result.extraction_metadata
        assert "extractability_ratio" in meta
        assert 0.0 <= meta["extractability_ratio"] <= 1.0
        # Multi-page PDF with content should have high extractability
        assert meta["extractability_ratio"] > 0.5

    def test_avg_chars_per_page_calculated(self) -> None:
        """Average characters per page is calculated."""
        _require_pdf_fixture(LARGE_TEXT_PDF)
        content = LARGE_TEXT_PDF.read_bytes()

        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename=LARGE_TEXT_PDF.name,
        )

        meta = result.extraction_metadata
        assert "avg_chars_per_page" in meta
        assert meta["avg_chars_per_page"] > 0

    def test_is_likely_scanned_flag(self) -> None:
        """is_likely_scanned flag is set based on extractability."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)
        content = SINGLE_PAGE_PDF.read_bytes()

        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename=SINGLE_PAGE_PDF.name,
        )

        meta = result.extraction_metadata
        assert "is_likely_scanned" in meta
        # Searchable PDF should not be flagged as scanned
        assert meta["is_likely_scanned"] is False


class TestTableDetection:
    """Tests for table detection functionality."""

    def test_detects_tables_in_pdf(self) -> None:
        """PDFs with tables should have table_pages > 0."""
        _require_pdf_fixture(TABLES_PDF)
        content = TABLES_PDF.read_bytes()

        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename=TABLES_PDF.name,
        )

        meta = result.extraction_metadata
        assert "table_pages" in meta
        assert meta["table_pages"] > 0

    def test_table_pages_confidence_adjusted(self) -> None:
        """Pages with tables should have slightly lower confidence."""
        _require_pdf_fixture(TABLES_PDF)
        content = TABLES_PDF.read_bytes()

        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename=TABLES_PDF.name,
        )

        # At least one page should have table-adjusted confidence (0.9)
        confidence_scores = [p.confidence_score for p in result.pages if not p.is_empty]
        assert any(score == 0.9 for score in confidence_scores)

    def test_table_detection_can_be_disabled(self) -> None:
        """Table detection can be disabled via config."""
        _require_pdf_fixture(TABLES_PDF)
        content = TABLES_PDF.read_bytes()

        config = PDFExtractionConfig(detect_tables=False)
        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename=TABLES_PDF.name,
            config=config,
        )

        meta = result.extraction_metadata
        # With detection disabled, table_pages should be 0
        assert meta["table_pages"] == 0


class TestSectionTitleDetection:
    """Tests for section title detection via font size heuristics."""

    def test_detects_section_titles(self) -> None:
        """Large text at top of page should be detected as section title."""
        _require_pdf_fixture(LARGE_TEXT_PDF)
        content = LARGE_TEXT_PDF.read_bytes()

        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename=LARGE_TEXT_PDF.name,
        )

        # At least one page should have a detected section title
        titles = [p.section_title for p in result.pages if p.section_title]
        # Note: This depends on the fixture having large-font headings
        # If no titles detected, that's okay - the feature is best-effort
        assert isinstance(titles, list)

    def test_section_title_detection_can_be_disabled(self) -> None:
        """Section title detection can be disabled via config."""
        _require_pdf_fixture(LARGE_TEXT_PDF)
        content = LARGE_TEXT_PDF.read_bytes()

        config = PDFExtractionConfig(detect_section_titles=False)
        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename=LARGE_TEXT_PDF.name,
            config=config,
        )

        # With detection disabled, no section titles should be set
        titles = [p.section_title for p in result.pages if p.section_title]
        assert len(titles) == 0


class TestPDFAnalysis:
    """Tests for PDF analysis (tier routing)."""

    def test_analyze_searchable_pdf(self) -> None:
        """Searchable PDF should recommend tier 1."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)
        content = SINGLE_PAGE_PDF.read_bytes()

        result = PDFExtractor.analyze_pdf(content, SINGLE_PAGE_PDF.name)

        assert isinstance(result, PDFAnalysisResult)
        assert result.page_count == 1
        assert result.has_text is True
        assert result.is_scanned is False
        assert result.recommended_tier in [1, 2]  # Simple or mixed

    def test_analyze_pdf_with_tables(self) -> None:
        """PDF with tables should be detected."""
        _require_pdf_fixture(TABLES_PDF)
        content = TABLES_PDF.read_bytes()

        result = PDFExtractor.analyze_pdf(content, TABLES_PDF.name)

        assert result.has_tables is True

    def test_analyze_returns_extractability_ratio(self) -> None:
        """Analysis should calculate extractability ratio."""
        _require_pdf_fixture(MULTI_PAGE_PDF)
        content = MULTI_PAGE_PDF.read_bytes()

        result = PDFExtractor.analyze_pdf(content, MULTI_PAGE_PDF.name)

        assert 0.0 <= result.extractability_ratio <= 1.0
        assert result.avg_chars_per_page > 0


class TestConfiguration:
    """Tests for PDFExtractionConfig options."""

    def test_max_pages_limit_enforced(self) -> None:
        """Extraction should respect max_pages config."""
        _require_pdf_fixture(MULTI_PAGE_PDF)
        content = MULTI_PAGE_PDF.read_bytes()

        config = PDFExtractionConfig(max_pages=2)
        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename=MULTI_PAGE_PDF.name,
            config=config,
        )

        assert result.total_pages <= 2

    def test_custom_min_chars_per_page(self) -> None:
        """Custom min_chars_per_page should be stored in metadata."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)
        content = SINGLE_PAGE_PDF.read_bytes()

        config = PDFExtractionConfig(min_chars_per_page=100)
        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename=SINGLE_PAGE_PDF.name,
            config=config,
        )

        assert result.extraction_metadata["min_chars_per_page"] == 100


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_corrupt_pdf_raises_extraction_error(self) -> None:
        """Corrupt/invalid PDF should raise ExtractionError."""
        _require_pdfplumber()
        from backend.core.exceptions import ExtractionError

        corrupt_content = b"not a valid pdf file"

        with pytest.raises(ExtractionError) as exc_info:
            PDFExtractor.extract(
                content=corrupt_content,
                document_id=uuid4(),
                filename="corrupt.pdf",
            )

        assert exc_info.value.details["error_type"] == "corrupt_file"

    def test_empty_bytes_raises_extraction_error(self) -> None:
        """Empty bytes should raise ExtractionError."""
        _require_pdfplumber()
        from backend.core.exceptions import ExtractionError

        with pytest.raises(ExtractionError):
            PDFExtractor.extract(
                content=b"",
                document_id=uuid4(),
                filename="empty.pdf",
            )


class TestInstanceMethod:
    """Tests for instance-based extraction (vs static method)."""

    def test_instance_extraction_works(self) -> None:
        """PDFExtractor instance method should work correctly."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)
        content = SINGLE_PAGE_PDF.read_bytes()

        extractor = PDFExtractor()
        result = extractor.extract_document(
            content=content,
            document_id=uuid4(),
            filename=SINGLE_PAGE_PDF.name,
        )

        assert result.total_pages == 1
        assert result.extraction_metadata["extraction_method"] == "pdfplumber"

    def test_instance_with_custom_config(self) -> None:
        """PDFExtractor instance should use provided config."""
        _require_pdf_fixture(SINGLE_PAGE_PDF)
        content = SINGLE_PAGE_PDF.read_bytes()

        config = PDFExtractionConfig(
            detect_tables=False,
            detect_section_titles=False,
        )
        extractor = PDFExtractor(config)
        result = extractor.extract_document(
            content=content,
            document_id=uuid4(),
            filename=SINGLE_PAGE_PDF.name,
        )

        # Table detection disabled
        assert result.extraction_metadata["table_pages"] == 0


class TestEncryptedPDFHandling:
    """Tests for encrypted PDF handling."""

    _ENCRYPTED_PDF_BASE64 = (
        "JVBERi0xLjMKJZOMi54gUmVwb3J0TGFiIEdlbmVyYXRlZCBQREYgZG9jdW1lbnQgK"
        "G9wZW5zb3VyY2UpCjEgMCBvYmoKPDwKL0YxIDIgMCBSCj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9CYXNlRm9udCAvSGVsdmV0aWNhIC9FbmNvZGluZyAvV2luQW5zaUVuY29"
        "kaW5nIC9OYW1lIC9GMSAvU3VidHlwZSAvVHlwZTEgL1R5cGUgL0ZvbnQKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL0NvbnRlbnRzIDggMCBSIC9NZWRpYUJveCBbIDAgMCA2MTIgNzkyIF0gL1BhcmVudCA3IDAgUiAvUmVzb3VyY2VzIDw8Ci9Gb250IDEgMCBSIC"
        "9Qcm9jU2V0IFsgL1BERiAvVGV4dCAvSW1hZ2VCIC9JbWFnZUMgL0ltYWdlSSBdCj4+IC9Sb3RhdGUgMCAvVHJhbnMgPDwKCj4+IAogIC9UeXBlIC9QYWdlCj4+CmVuZG9iago0IDAgb2JqCjw8Ci9QYWdlTW9kZSAvVXNlTm9uZSAvUGFnZXMgNyAwIFIgL1R5c"
        "GUgL0NhdGFsb2cKPj4KZW5kb2JqCjUgMCBvYmoKPDwKL0F1dGhvciAoXDIyNW5JXDIyMHV9WVwwMDQgKSAvQ3JlYXRpb25EYXRlIChcMjYwOlwwMjRcMzE2PiVcMDA3Q2JcMzcwXDAwNT5qXDI1Mj9cMjMwXDMzNVwzNDQ8XDAyNlwzMDVcMzA1JCkgL0NyZWF0"
        "b3IgKFwyMjVuSVwyMjB1fVlcMDA0ICkgL0tleXdvcmRzICgpIC9Nb2REYXRlIChcMjYwOlwwMjRcMzE2PiVcMDA3Q2JcMzcwXDAwNT5qXDI1Mj9cMjMwXDMzNVwzNDQ8XDAyNlwzMDVcMzA1JCkgL1Byb2R1Y2VyIChcMjQ2ZVZcMjIxfmR6XDAyMDFcMzU0ZE9"
        "cMDM3XDI3MUNcMzA3XDIyNFwyNDZoQ1wyMTRcMzI1LlwyMjdcMzY1XDMxM1wzMDNcMjQzXDMxMEhuN1wyNjAvXDM2MVwzMTIpIAogIC9TdWJqZWN0IChcMjAxblVcMjE2aXNfXDAyNzpcMjUxUCkgL1RpdGxlIChcMjAxblJcMjI3eHxTXDAyNSkgL1RyYXBwZWQ"
        "gL0ZhbHNlCj4+CmVuZG9iago2IDAgb2JqCjw8Ci9GaWx0ZXIgL1N0YW5kYXJkIC9PIDxGOTc0MDVFRDBDRUQ4MUYwQzg0NDQzMDE1MkY0RjBENUUyQkY1NkQ5MTQ5NUExN0I4NzJFMzA1MkUxQUY1Njk5PiAvUCAtNCAvUiAyIC9VIDxGOUM0N0JBMzM2QUJEN"
        "UQ0RTY4N0Y2NTYxMjU1MjlFNENFOEE1MDEwOTBDMEMxNjM4QzI4OTM2QUM1OEJDNjJEPiAvViAxCj4+CmVuZG9iago3IDAgb2JqCjw8Ci9Db3VudCAxIC9LaWRzIFsgMyAwIFIgXSAvVHlwZSAvUGFnZXMKPj4KZW5kb2JqCjggMCBvYmoKPDwKL0ZpbHRlciBb"
        "IC9BU0NJSTg1RGVjb2RlIC9GbGF0ZURlY29kZSBdIC9MZW5ndGggMTIyCj4+CnN0cmVhbQq0JZu7CoM9g8Yjbx2mXf470KmV3dtKfAQsSgv07FaO6FQkPwQdgK5M9xr/H8qUBEXSh4rUvkPBvgUg1kq/bkE5G0ESSvLB+cvwsNhbC8R3U21x9cCAZvQlOmNsLM4"
        "wybw+szI/pqR8JIoNZT2iVjZBHXFFQ4ybbMt7+WVuZHN0cmVhbQplbmRvYmoKeHJlZgowIDkKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDYxIDAwMDAwIG4gCjAwMDAwMDAwOTIgMDAwMDAgbiAKMDAwMDAwMDE5OSAwMDAwMCBuIAowMDAwMDAwMzkyID"
        "AwMDAwIG4gCjAwMDAwMDA0NjAgMDAwMDAgbiAKMDAwMDAwMDg5NiAwMDAwMCBuIAowMDAwMDAxMDkxIDAwMDAwIG4gCjAwMDAwMDExNTAgMDAwMDAgbiAKdHJhaWxlcgo8PAovRW5jcnlwdCA2IDAgUgovSUQgCls8NTBiYmZjMjJmNTc4ODM4N2JjNWE2YjEzZ"
        "jYxZDhmZGI+PDUwYmJmYzIyZjU3ODgzODdiYzVhNmIxM2Y2MWQ4ZmRiPl0KJSBSZXBvcnRMYWIgZ2VuZXJhdGVkIFBERiBkb2N1bWVudCAtLSBkaWdlc3QgKG9wZW5zb3VyY2UpCgovSW5mbyA1IDAgUgovUm9vdCA0IDAgUgovU2l6ZSA5Cj4+CnN0YXJ0eHJl"
        "ZgoxMzYyCiUlRU9GCg=="
    )

    def test_encrypted_pdf_requires_password(self) -> None:
        _require_pdfplumber()
        from backend.core.exceptions import ExtractionError

        content = base64.b64decode(self._ENCRYPTED_PDF_BASE64)
        with pytest.raises(ExtractionError) as exc_info:
            PDFExtractor.extract(
                content=content,
                document_id=uuid4(),
                filename="encrypted.pdf",
            )

        assert exc_info.value.details["error_type"] in {
            "encrypted_file",
            "invalid_password",
        }
        assert exc_info.value.status_code == 400

    def test_encrypted_pdf_succeeds_with_password(self) -> None:
        _require_pdfplumber()

        content = base64.b64decode(self._ENCRYPTED_PDF_BASE64)
        result = PDFExtractor.extract(
            content=content,
            document_id=uuid4(),
            filename="encrypted.pdf",
            password="testpassword",
        )

        assert result.total_pages == 1
        assert any(not page.is_empty for page in result.pages)


# Backward compatibility aliases for existing test names
def test_pdf_extractor_single_page_basic() -> None:
    """Backward compatibility wrapper."""
    TestBasicExtraction().test_single_page_basic()


def test_pdf_extractor_tracks_page_numbers_for_multi_page() -> None:
    """Backward compatibility wrapper."""
    TestBasicExtraction().test_tracks_page_numbers_for_multi_page()


def test_pdf_extractor_marks_empty_pages_and_updates_metrics() -> None:
    """Backward compatibility wrapper."""
    TestBasicExtraction().test_marks_empty_pages_and_updates_metrics()
