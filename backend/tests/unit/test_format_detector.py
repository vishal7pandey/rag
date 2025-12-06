import pytest

from backend.core.exceptions import ExtractionError
from backend.core.format_detector import FileFormat, FormatDetector


def test_detector_recognizes_pdf() -> None:
    detector = FormatDetector()
    pdf_content = b"%PDF-1.4\n%test"
    fmt = detector.detect_format("doc.pdf", pdf_content)
    assert fmt == FileFormat.PDF


def test_detector_recognizes_txt() -> None:
    detector = FormatDetector()
    text_content = b"This is plain text content"
    fmt = detector.detect_format("doc.txt", text_content)
    assert fmt == FileFormat.TEXT


def test_detector_recognizes_markdown() -> None:
    detector = FormatDetector()
    md_content = b"# Title\n\nContent here"
    fmt = detector.detect_format("doc.md", md_content)
    assert fmt == FileFormat.MARKDOWN


def test_detector_rejects_unsupported_format() -> None:
    detector = FormatDetector()
    with pytest.raises(ExtractionError) as exc_info:
        detector.detect_format("script.exe", b"MZ\x90")

    err = exc_info.value
    assert err.details.get("error_type") == "unsupported_format"
    assert err.details.get("filename") == "script.exe"
